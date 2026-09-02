from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.security import InvalidTokenError, decode_token
from app.db.session import AsyncSessionLocal
from app.models.workspace import Workspace
from app.repositories.dialog_repository import DialogRepository
from app.services.dialog_service import DialogService
from app.ws.manager import ws_manager

router = APIRouter(tags=["dialogs-ws"])


async def _send_error(websocket: WebSocket, detail: str) -> None:
    try:
        await websocket.send_json({"type": "error", "detail": detail})
    except Exception:
        pass


@router.websocket("/workspaces/{workspace_id}/dialogs/{dialog_id}/ws")
async def dialog_websocket(websocket: WebSocket, workspace_id: UUID, dialog_id: UUID, token: str):
    async with AsyncSessionLocal() as db:
        try:
            payload = decode_token(token, expected_type="access")
            user_id = UUID(payload["sub"])
        except (InvalidTokenError, KeyError, ValueError, TypeError):
            await websocket.close(code=4401)
            return

        workspace = await db.get(Workspace, workspace_id)
        if workspace is None or workspace.owner_id != user_id:
            await websocket.close(code=4403)
            return

        dialog_repo = DialogRepository(db)
        dialog = await dialog_repo.get_by_id(dialog_id, workspace_id)
        if dialog is None:
            await websocket.close(code=4404)
            return

    await websocket.accept()
    await ws_manager.connect(dialog_id, websocket)

    try:
        while True:
            payload = await websocket.receive_json()
            msg_type = payload.get("type")

            async with AsyncSessionLocal() as db:
                dialog_service = DialogService(db)
                dialog = await dialog_service.get_owned(dialog_id, workspace_id)

                if msg_type == "reply":
                    content = (payload.get("content") or "").strip()
                    if not content:
                        await _send_error(websocket, "Сообщение не может быть пустым")
                        continue
                    try:
                        await dialog_service.owner_reply(dialog, content)
                    except Exception:
                        await _send_error(websocket, "Не удалось отправить сообщение")

                elif msg_type == "close_dialog":
                    try:
                        await dialog_service.close(dialog)
                    except Exception:
                        await _send_error(websocket, "Не удалось закрыть диалог")

                else:
                    await _send_error(websocket, f"Неизвестный тип сообщения: {msg_type}")

    except WebSocketDisconnect:
        pass
    except Exception:
        await _send_error(websocket, "Внутренняя ошибка сервера")
    finally:
        await ws_manager.disconnect(dialog_id, websocket)