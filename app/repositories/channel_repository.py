from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.channel import Channel
from app.schemas.channel import ChannelCreate, ChannelUpdate


class ChannelRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, channel_id: UUID, workspace_id: UUID) -> Channel | None:
        result = await self.db.execute(
            select(Channel).where(
                Channel.id == channel_id,
                Channel.workspace_id == workspace_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_workspace(self, workspace_id: UUID) -> list[Channel]:
        result = await self.db.execute(
            select(Channel)
            .where(Channel.workspace_id == workspace_id)
            .order_by(Channel.created_at.desc())
        )
        return list(result.scalars().all())

    async def create(self, workspace_id: UUID, payload: ChannelCreate) -> Channel:
        channel_name = payload.name or f"{payload.type.value.capitalize()} Channel"

        channel = Channel(
            workspace_id=workspace_id,
            name=channel_name,
            type=payload.type,
            credentials=payload.credentials,
        )
        self.db.add(channel)
        await self.db.flush()
        return channel

    async def update(self, channel: Channel, payload: ChannelUpdate) -> Channel:
        data = payload.model_dump(exclude_unset=True)
        for field, value in data.items():
            if value is not None:
                setattr(channel, field, value)
        await self.db.flush()
        return channel

    async def delete(self, channel: Channel) -> None:
        await self.db.delete(channel)
        await self.db.flush()