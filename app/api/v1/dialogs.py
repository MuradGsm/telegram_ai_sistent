from uuid import UUID

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from fastapi import (
    APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_owned_workspace
from app.core.enums import DialogStatus
from app.core.security import InvalidTokenError, decode_token
from app.db.session import get_db
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.dialog import DialogDetailOut, DialogOut, OwnerReplyCreate
from app.services.dialog_service import DialogService
from app.services.workspace_service import WorkspaceService
from app.ws.manager import ws_manager


router = APIRouter(prefix="/workspaces/{workspace_id}/dialogs", tags=["dialogs"])


def get_dialog_service(db: AsyncSession = Depends(get_db)) -> DialogService:
    return DialogService(db)


@router.get("", response_model=list[DialogOut])
async def list_dialogs(
    workspace: Workspace = Depends(get_owned_workspace),
    status_filter: DialogStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: DialogService = Depends(get_dialog_service),
):
    return await service.list_for_workspace(workspace.id, status_filter, limit, offset)


@router.get("/{dialog_id}", response_model=DialogDetailOut)
async def get_dialog(
    dialog_id: UUID,
    workspace: Workspace = Depends(get_owned_workspace),
    service: DialogService = Depends(get_dialog_service),
):
    return await service.get_owned_with_messages(dialog_id, workspace.id)


@router.post("/{dialog_id}/reply", status_code=status.HTTP_204_NO_CONTENT)
async def reply_to_dialog(
    dialog_id: UUID,
    payload: OwnerReplyCreate,
    workspace: Workspace = Depends(get_owned_workspace),
    service: DialogService = Depends(get_dialog_service),
):
    if not workspace.telegram_bot_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram bot is not connected to this workspace",
        )

    dialog = await service.get_owned(dialog_id, workspace.id)

    # 1. Сначала отправляем сообщение в Telegram
    async with Bot(token=workspace.telegram_bot_token) as bot:
        try:
            await bot.send_message(
                chat_id=dialog.customer_telegram_id, text=payload.content
            )
        except TelegramAPIError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to send message via Telegram: {exc.message}",
            ) from exc

    # 2. Только при успешной доставке сохраняем ответ в базу данных
    await service.owner_reply(dialog, payload.content)


@router.post("/{dialog_id}/close", response_model=DialogOut)
async def close_dialog(
    dialog_id: UUID,
    workspace: Workspace = Depends(get_owned_workspace),
    service: DialogService = Depends(get_dialog_service),
):
    dialog = await service.get_owned(dialog_id, workspace.id)
    return await service.close(dialog)


@router.websocket("/{dialog_id}/ws")
async def dialog_ws(
    websocket: WebSocket,
    workspace_id: UUID,
    dialog_id: UUID,
    token: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    # Принимаем соединение до валидации, чтобы websocket.close() отправлял корректный WS-код закрытия
    await websocket.accept()

    if token is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        payload = decode_token(token, expected_type="access")
        user_id = UUID(payload["sub"])
    except (InvalidTokenError, KeyError, ValueError, TypeError):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        workspace = await WorkspaceService(db).get_owned(workspace_id, user.id)
    except HTTPException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    service = DialogService(db)
    try:
        dialog = await service.get_owned(dialog_id, workspace.id)
    except HTTPException:
        await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
        return

    await ws_manager.connect(dialog_id, websocket)

    try:
        while True:
            raw = await websocket.receive_json()
            msg_type = raw.get("type")

            if msg_type == "reply":
                content = (raw.get("content") or "").strip()
                if not content or len(content) > 4000:
                    await websocket.send_json({"type": "error", "detail": "Invalid content"})
                    continue
                if not workspace.telegram_bot_token:
                    await websocket.send_json(
                        {"type": "error", "detail": "Telegram bot is not connected"}
                    )
                    continue

                async with Bot(token=workspace.telegram_bot_token) as bot:
                    try:
                        await bot.send_message(
                            chat_id=dialog.customer_telegram_id, text=content
                        )
                    except TelegramAPIError as exc:
                        await websocket.send_json(
                            {"type": "error", "detail": f"Telegram error: {exc.message}"}
                        )
                        continue

                await service.owner_reply(dialog, content)

            elif msg_type == "close_dialog":
                await service.close(dialog)

            else:
                await websocket.send_json({"type": "error", "detail": "Unknown message type"})

    except WebSocketDisconnect:
        pass
    finally:
        # disconnect — синхронный метод у DialogConnectionManager
        ws_manager.disconnect(dialog_id, websocket)