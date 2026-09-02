from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.external.redis import redis_client
from app.core.enums import ChannelType
from app.models.channel import Channel
from app.services.dialog_service import DialogService
from app.providers.registry import get_provider

router = APIRouter(tags=["telegram"])


@router.post("/telegram/webhook/{channel_id}")
async def telegram_webhook(
    channel_id: UUID,
    update: dict,
    x_telegram_bot_api_secret_token: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    channel = await db.get(Channel, channel_id)
    if channel is None or channel.type != ChannelType.TELEGRAM:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")

    expected_secret = channel.credentials.get("webhook_secret")
    if expected_secret and x_telegram_bot_api_secret_token != expected_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid secret token")

    provider = get_provider(channel.type)
    incoming = provider.parse_incoming(update)
    if incoming is None:
        return {"ok": True}

    if incoming.external_message_id:
        dedup_key = f"tg:update:{channel_id}:{incoming.external_message_id}"
        is_new = await redis_client.set(dedup_key, "1", ex=86400, nx=True)
        if not is_new:
            return {"ok": True}

    dialog_service = DialogService(db)
    _, bot_reply = await dialog_service.handle_incoming_customer_message(
        workspace_id=channel.workspace_id,
        channel_id=channel.id,
        external_customer_id=incoming.external_customer_id,
        customer_display_name=incoming.customer_display_name,
        text=incoming.text,
    )

    try:
        await provider.send_reply(channel.credentials, incoming.external_customer_id, bot_reply)
    except Exception:
        pass

    return {"ok": True}