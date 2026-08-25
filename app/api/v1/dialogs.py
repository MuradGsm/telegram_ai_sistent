from uuid import UUID

from aiogram import Bot
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_owned_workspace
from app.core.enums import DialogStatus
from app.db.session import get_db
from app.models.workspace import Workspace
from app.schemas.dialog import DialogDetailOut, DialogOut, OwnerReplyCreate
from app.services.dialog_service import DialogService


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
    return await service.get_owned(dialog_id, workspace.id)


@router.post("/{dialog_id}/reply", status_code=status.HTTP_204_NO_CONTENT)
async def reply_to_dialog(
    dialog_id: UUID,
    payload: OwnerReplyCreate,
    workspace: Workspace = Depends(get_owned_workspace),
    service: DialogService = Depends(get_dialog_service),
):
    dialog = await service.get_owned(dialog_id, workspace.id)
    await service.owner_reply(dialog, payload.content)

    if workspace.telegram_bot_token:
        bot = Bot(token=workspace.telegram_bot_token)
        try:
            await bot.send_message(chat_id=dialog.customer_telegram_id, text=payload.content)
        finally:
            await bot.session.close()


@router.post("/{dialog_id}/close", response_model=DialogOut)
async def close_dialog(
    dialog_id: UUID,
    workspace: Workspace = Depends(get_owned_workspace),
    service: DialogService = Depends(get_dialog_service),
):
    dialog = await service.get_owned(dialog_id, workspace.id)
    return await service.close(dialog)