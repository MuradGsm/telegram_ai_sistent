from uuid import UUID

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Update
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.conf import settings
from app.db.session import get_db
from app.repositories.workspace_repository import WorkspaceRepository
from app.services.dialog_service import DialogService

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/webhook/{workspace_id}")
async def telegram_webhook(
    workspace_id: UUID,
    update: dict,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    # 1. Валидация секретного токена Telegram Webhook
    if (
        settings.telegram_webhook_secret
        and x_telegram_bot_api_secret_token != settings.telegram_webhook_secret
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid secret token",
        )

    # 2. Проверка воркспейса
    workspace_repo = WorkspaceRepository(db)
    workspace = await workspace_repo.get_by_id(workspace_id)

    # Если воркспейс удалён или бот отключён — отдаём 200 OK, чтобы Telegram
    # прекратил повторные попытки (retry) на мёртвый эндпоинт
    if not workspace or not workspace.is_bot_active or not workspace.telegram_bot_token:
        return {"ok": True, "detail": "Bot disabled or workspace not found"}

    parsed_update = Update.model_validate(update)
    message = parsed_update.message

    if message is None or message.text is None:
        return {"ok": True}

    dialog_service = DialogService(db)

    # 3. Обработка входящего сообщения и генерация RAG/LLM ответа
    dialog, reply_text = await dialog_service.handle_incoming_customer_message(
        workspace_id=workspace_id,
        customer_telegram_id=message.from_user.id,
        customer_display_name=message.from_user.full_name,
        text=message.text,
    )

    # 4. Отправка ответа клиенту
    if reply_text:
        async with Bot(token=workspace.telegram_bot_token) as bot:
            try:
                await bot.send_message(chat_id=message.chat.id, text=reply_text)
            except TelegramAPIError:
                # Клиент мог заблокировать бота или удалить чат —
                # не роняем обработку вебхука, просто не доставляем ответ.
                pass

    return {"ok": True}