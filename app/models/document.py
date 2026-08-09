from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import DocumentStatus
from app.db.database import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.workspace import Workspace


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = 'documents'

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey('workspaces.id', ondelete='CASCADE')
    )
    workspace: Mapped[Workspace] = relationship(back_populates='documents')

    file_name: Mapped[str] = mapped_column(String(500))
    r2_object_key: Mapped[str] = mapped_column(String(1000))
    content_type: Mapped[str] = mapped_column(String(100))

    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name='document_status_enum'),
        default=DocumentStatus.UPLOADED,
        server_default=DocumentStatus.UPLOADED.value,
    )

    chunk_count: Mapped[int] = mapped_column(default=0, server_default=text('0'))
    error_message: Mapped[str | None] = mapped_column(String(1000))