from __future__ import annotations

import secrets
from typing import Any
from uuid import UUID

import httpx
from aiogram import Bot
from fastapi import HTTPException, status

from app.core.conf import settings
from app.core.enums import ChannelType
from app.providers.base import ChannelProvider, IncomingMessage


class TelegramProvider(ChannelProvider):
    channel_type = ChannelType.TELEGRAM

    async def validate_credentials(self, credentials: dict[str, Any]) -> dict[str, Any]:
        token = credentials.get("bot_token")
        if not token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="bot_token is required for Telegram channel",
            )

        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.get(f"https://api.telegram.org/bot{token}/getMe")
                data = resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Could not reach or parse Telegram API",
                ) from exc

            if not data.get("ok"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid Telegram bot token",
                )

        credentials["bot_username"] = data["result"]["username"]
        return credentials

    async def setup_webhook(self, channel_id: UUID, credentials: dict[str, Any]) -> dict[str, Any]:
        token = credentials["bot_token"]
        webhook_secret = credentials.get("webhook_secret") or secrets.token_urlsafe(32)

        webhook_url = f"{settings.public_base_url}/telegram/webhook/{channel_id}"
        payload = {"url": webhook_url, "secret_token": webhook_secret}

        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.post(
                    f"https://api.telegram.org/bot{token}/setWebhook", json=payload
                )
                data = resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to reach Telegram API for setting webhook",
                ) from exc

            if not data.get("ok"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to set Telegram webhook: {data.get('description', 'Unknown error')}",
                )

        credentials["webhook_secret"] = webhook_secret
        return credentials

    async def teardown_webhook(self, credentials: dict[str, Any]) -> None:
        token = credentials.get("bot_token")
        if not token:
            return
        async with httpx.AsyncClient(timeout=5) as client:
            try:
                await client.post(f"https://api.telegram.org/bot{token}/deleteWebhook")
            except httpx.HTTPError:
                pass

    def parse_incoming(self, payload: dict[str, Any]) -> IncomingMessage | None:
        message = payload.get("message")
        if not message or "text" not in message:
            return None

        from_user = message.get("from", {})
        first_name = from_user.get("first_name", "")
        last_name = from_user.get("last_name", "")
        display_name = f"{first_name} {last_name}".strip() or None

        return IncomingMessage(
            external_customer_id=str(from_user.get("id")),
            customer_display_name=display_name,
            text=message["text"],
            external_message_id=str(payload.get("update_id")),
        )

    async def send_reply(self, credentials: dict[str, Any], external_customer_id: str, text: str) -> None:
        token = credentials.get("bot_token")
        if not token:
            return
        async with Bot(token=token) as bot:
            await bot.send_message(chat_id=external_customer_id, text=text)