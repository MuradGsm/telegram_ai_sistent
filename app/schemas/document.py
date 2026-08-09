from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import DocumentStatus


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    file_name: str
    content_type: str
    status: DocumentStatus
    chunk_count: int
    error_message: str | None = None
    created_at: datetime


class DocumentUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_name: str
    status: DocumentStatus


class DocumentRename(BaseModel):
    file_name: str = Field(min_length=1, max_length=500)