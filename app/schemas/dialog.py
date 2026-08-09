from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict
from app.core.enums import DialogStatus, MessageSender


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sender: MessageSender
    content: str
    tokens_used: int | None = None
    confidence_score: float | None = None
    source_chunk_ids: list[UUID] | None = None
    created_at: datetime


class DialogOut(BaseModel):
    model_config =  ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    customer_telegram_id: int
    customer_display_name: str | None = None
    status: DialogStatus
    created_at: datetime


class DialogDetailOut(DialogOut):
    messages: list[MessageOut] = []


class DialogListParam(BaseModel):
    status: DialogStatus | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class OwnerReplyCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)