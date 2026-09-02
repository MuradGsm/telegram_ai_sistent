import uuid
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import ChannelType


class ChannelCreate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    type: ChannelType
    credentials: dict[str, Any] = Field(default_factory=dict)


class ChannelUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    credentials: dict[str, Any] | None = None


class ChannelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    type: ChannelType
    credentials: dict[str, Any]