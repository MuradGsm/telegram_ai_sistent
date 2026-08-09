from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import DialogStatus, MessageSender
from app.db.database import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.workspace import Workspace


class Dialog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = 'dialogs'

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey('workspaces.id', ondelete='CASCADE')
    )
    workspace: Mapped[Workspace] = relationship(back_populates='dialogs')

    customer_telegram_id: Mapped[int] = mapped_column(BigInteger)
    customer_display_name: Mapped[str | None] = mapped_column(String(255))

    status: Mapped[DialogStatus] = mapped_column(
        Enum(DialogStatus, name='dialog_status_enum'),
        default=DialogStatus.OPEN_AUTO,
        server_default=DialogStatus.OPEN_AUTO.value,
    )

    messages: Mapped[list[Message]] = relationship(
        back_populates='dialog',
        cascade='all, delete-orphan',
        order_by=lambda: Message.created_at, 
    )

    __table_args__ = (
        Index('ix_dialogs_workspace_customer', 'workspace_id', 'customer_telegram_id'),
    )


class Message(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = 'messages'

    dialog_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey('dialogs.id', ondelete='CASCADE'), index=True
    )
    dialog: Mapped[Dialog] = relationship(back_populates='messages')

    sender: Mapped[MessageSender] = mapped_column(
        Enum(MessageSender, name='message_sender_enum')
    )
    content: Mapped[str] = mapped_column(Text)

    tokens_used: Mapped[int | None] = mapped_column()
    confidence_score: Mapped[float | None] = mapped_column(Numeric(3, 2))

    source_chunk_ids: Mapped[list[uuid.UUID] | None] = mapped_column(ARRAY(Uuid))