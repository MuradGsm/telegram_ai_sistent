from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Enum, ForeignKey, String, Uuid, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import ChannelType
from app.db.database import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.workspace import Workspace


class Channel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "channels"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    workspace: Mapped[Workspace] = relationship(back_populates="channels")

    type: Mapped[ChannelType] = mapped_column(
        Enum(
            ChannelType,
            name="channel_type_enum",
            values_callable=lambda obj: [e.value for e in obj],
        )
    )
    name: Mapped[str] = mapped_column(String(255))
    credentials: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)