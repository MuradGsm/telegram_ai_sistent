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
    owner_telegram_id: int | None = Field(default=None, ge=1) 


class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    timezone: str
    is_bot_active: bool
    telegram_bot_username: str | None = None
    owner_telegram_id: int | None = None
    plan_tier: PlanTier
    monthly_message_limit: int
    messages_used_this_period: int
    created_at: datetime


class WorkspaceConnectBot(BaseModel):
    telegram_bot_token: str = Field(min_length=20, max_length=255)