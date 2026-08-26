from uuid import UUID

from aiogram import Bot
from aiogram.types import Update
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.workspace_repository import WorkspaceRepository
from app.services.dialog_service import DialogService


router = APIRouter(prefix='/telegram', tags=['telegram'])

@router.post("/webhook/{workspace_id}")
async def telegram_webhook(
    workspace_id: UUID,
    update: dict,
    db: AsyncSession = Depends(get_db)
):
    workspace_repo = WorkspaceRepository(db)
    workspace = await workspace_repo.get_by_id(workspace_id)

    if workspace is None or not workspace.is_bot_active or not workspace.telegram_bot_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bot not configured"
        )

    parsed_update = Update.model_validate(update)
    message = parsed_update.message

    if message is None or message.text is None:
        return {"ok": True}

    dialog_service = DialogService(db)

    dialog, reply_text = await dialog_service.handle_incoming_customer_message(
        workspace_id=workspace_id,
        customer_telegram_id=message.from_user.id,
        customer_display_name=message.from_user.full_name,
        text=message.text
    )

    if reply_text:
        bot = Bot(token=workspace.telegram_bot_token)
        try:
            await bot.send_message(chat_id=message.chat.id, text=reply_text)
        finally:
            await bot.session.close()
            
    return {"ok": True}