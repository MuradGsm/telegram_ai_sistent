from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import SubscriptionStatus
from app.db.database import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.workspace import Workspace


class Subscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = 'subscriptions'

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey('workspaces.id', ondelete='CASCADE'), unique=True
    )
    workspace: Mapped[Workspace] = relationship(back_populates='subscription')

    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(
            SubscriptionStatus,
            name='subscription_status_enum',
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=SubscriptionStatus.TRIALING,
        server_default=text("'trialing'"),
    )

    price_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal('0.00'), server_default=text('0.00')
    )
    price_currency: Mapped[str] = mapped_column(
        String(3), default='USD', server_default=text("'USD'")
    )

    external_provider: Mapped[str | None] = mapped_column(String(50))
    external_subscription_id: Mapped[str | None] = mapped_column(String(255), index=True)

    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))