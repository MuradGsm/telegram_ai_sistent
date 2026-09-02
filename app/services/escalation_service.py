from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ChannelType
from app.models.channel import Channel
from app.models.dialog import Dialog
from app.models.workspace import Workspace

logger = logging.getLogger(__name__)


async def _find_workspace_telegram_bot_token(db: AsyncSession, workspace_id) -> str | None:
    result = await db.execute(
        select(Channel.credentials)
        .where(Channel.workspace_id == workspace_id, Channel.type == ChannelType.TELEGRAM)
        .limit(1)
    )
    credentials = result.scalar_one_or_none()
    if not credentials:
        return None
    return credentials.get("bot_token")


async def notify_owner_escalation(
    db: AsyncSession, workspace: Workspace, dialog: Dialog, question: str
) -> None:
    if not workspace.owner_telegram_id:
        logger.warning(
            f"Cannot send escalation notification for workspace {workspace.id}: "
            f"owner_telegram_id is not set"
        )
        return

    bot_token = await _find_workspace_telegram_bot_token(db, workspace.id)
    if not bot_token:
        logger.warning(
            f"Cannot send escalation notification for workspace {workspace.id}: "
            f"no connected Telegram channel to send notification through"
        )
        return

    customer_info = dialog.customer_display_name or f"ID: {dialog.external_customer_id}"

    text = (
        "⚠️ Требуется ваше внимание\n\n"
        f"Workspace: {workspace.name}\n"
        f"Клиент: {customer_info}\n\n"
        f"Вопрос: {question}\n\n"
        f"Диалог ID: {dialog.id}"
    )

    try:
        async with Bot(token=bot_token) as bot:
            await bot.send_message(chat_id=workspace.owner_telegram_id, text=text)
    except TelegramAPIError as exc:
        logger.error(
            f"Failed to send escalation notification to owner {workspace.owner_telegram_id}: {exc}"
        )