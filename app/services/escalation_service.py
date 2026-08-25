from aiogram import Bot

from app.core.conf import settings
from app.models.dialog import Dialog
from app.models.workspace import Workspace

_service_bot: Bot | None = None

def _get_service_bot() -> Bot:
    global _service_bot
    if _service_bot is None:
        _service_bot = Bot(token=settings.bot_token)
    return _service_bot


async def notify_owner_escalation(workspace: Workspace, dialog: Dialog, question: str) -> None:
    if workspace.owner_telegram_id is None:
        return

    text = (
        f"⚠️ Требуется ваше внимание\n\n"
        f"Workspace: {workspace.name}\n"
        f"Клиент: {dialog.customer_display_name or dialog.customer_telegram_id}\n\n"
        f"Вопрос: {question}\n\n"
        f"Диалог ID: {dialog.id}"
    )

    bot  = _get_service_bot()
    await bot.send_message(chat_id=workspace.owner_telegram_id, text=text)

    