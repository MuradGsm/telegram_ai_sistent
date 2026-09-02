from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import PlanTier


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    timezone: str = Field(default="Asia/Baku", max_length=64)


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    timezone: str | None = Field(default=None, max_length=64)
    owner_telegram_id: str | None = Field(default=None, max_length=64)


class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    timezone: str
    plan_tier: PlanTier
    monthly_message_limit: int
    messages_used_this_period: int
    owner_telegram_id: str | None = None
    created_at: datetime


class WorkspaceListOut(WorkspaceOut):
    active_channels_count: int = 0