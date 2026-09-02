from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.core.enums import ChannelType
from app.providers.base import ChannelProvider, IncomingMessage


class WebProvider(ChannelProvider):
    channel_type = ChannelType.WEB

    async def validate_credentials(self, credentials: dict[str, Any]) -> dict[str, Any]:
        allowed_origin = credentials.get("allowed_origin")
        if not allowed_origin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="allowed_origin is required for Web channel",
            )
        return credentials

    async def setup_webhook(self, channel_id: UUID, credentials: dict[str, Any]) -> dict[str, Any]:
        # Нет внешнего API - вебхук не нужен, доставка идёт через ws_manager
        return credentials

    async def teardown_webhook(self, credentials: dict[str, Any]) -> None:
        return None

    def parse_incoming(self, payload: dict[str, Any]) -> IncomingMessage | None:
        text = payload.get("text")
        if not text:
            return None

        return IncomingMessage(
            external_customer_id=payload["visitor_id"],
            customer_display_name=payload.get("display_name"),
            text=text,
            external_message_id=payload.get("client_message_id"),
        )

    async def send_reply(self, credentials: dict[str, Any], external_customer_id: str, text: str) -> None:
        # Доставка уже произошла через ws_manager.broadcast внутри dialog_service
        return None