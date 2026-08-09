from __future__ import annotations

from typing import TYPE_CHECKING
from sqlalchemy import String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.db.mixins import UUIDPrimaryKeyMixin, TimestampMixin 

if TYPE_CHECKING:
    from app.models.workspace import Workspace


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))

    workspaces: Mapped[list[Workspace]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )