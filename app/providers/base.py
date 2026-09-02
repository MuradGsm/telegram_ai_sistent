from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.core.enums import ChannelType


@dataclass
class IncomingMessage:
    external_customer_id: str
    customer_display_name: str | None
    text: str
    external_message_id: str | None = None  # для идемпотентности


class ChannelProvider(ABC):
    channel_type: ChannelType

    @abstractmethod
    async def validate_credentials(self, credentials: dict[str, Any]) -> dict[str, Any]:
        """Проверяет креды у внешнего API, возвращает обогащённый dict (или райзит HTTPException)."""

    @abstractmethod
    async def setup_webhook(self, channel_id: UUID, credentials: dict[str, Any]) -> dict[str, Any]:
        """Настраивает вебхук, возвращает креды с доп. полями (например webhook_secret)."""

    @abstractmethod
    async def teardown_webhook(self, credentials: dict[str, Any]) -> None:
        ...

    @abstractmethod
    def parse_incoming(self, payload: dict[str, Any]) -> IncomingMessage | None:
        ...

    @abstractmethod
    async def send_reply(self, credentials: dict[str, Any], external_customer_id: str, text: str) -> None:
        ...