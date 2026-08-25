from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, Uuid, text, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import PlanTier
from app.db.database import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.dialog import Dialog
    from app.models.document import Document
    from app.models.user import User
    from app.models.subscription import Subscription


class Workspace(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = 'workspaces'

    name: Mapped[str] = mapped_column(String(255))
    timezone: Mapped[str] = mapped_column(String(64), default='Asia/Baku', server_default='Asia/Baku')

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey('users.id', ondelete='CASCADE')
    )
    owner: Mapped[User] = relationship(back_populates='workspaces')

    telegram_bot_token: Mapped[str | None] = mapped_column(String(255))
    telegram_bot_username: Mapped[str | None] = mapped_column(String(255))
    is_bot_active: Mapped[bool] = mapped_column(default=False, server_default=text('false'))
    owner_telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    plan_tier: Mapped[PlanTier] = mapped_column(
        Enum(PlanTier, name='plan_tier_enum', values_callable=lambda obj: [e.value for e in obj]),
        default=PlanTier.FREE,
        server_default=PlanTier.FREE.value,
    )
    monthly_message_limit: Mapped[int] = mapped_column(default=100, server_default=text('100'))
    messages_used_this_period: Mapped[int] = mapped_column(default=0, server_default=text('0'))

    documents: Mapped[list[Document]] = relationship(
        back_populates='workspace', cascade='all, delete-orphan'
    )
    dialogs: Mapped[list[Dialog]] = relationship(
        back_populates='workspace', cascade='all, delete-orphan'
    )

    subscription: Mapped[Subscription | None] = relationship(back_populates='workspace')