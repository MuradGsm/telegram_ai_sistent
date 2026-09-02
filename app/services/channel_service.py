from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.channel import Channel
from app.repositories.channel_repository import ChannelRepository
from app.schemas.channel import ChannelCreate, ChannelUpdate
from app.providers.registry import get_provider


class ChannelService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ChannelRepository(db)

    async def create(self, workspace_id: UUID, payload: ChannelCreate) -> Channel:
        provider = get_provider(payload.type)

        payload.credentials = await provider.validate_credentials(payload.credentials)
        channel = await self.repo.create(workspace_id, payload)

        channel.credentials = await provider.setup_webhook(channel.id, channel.credentials)
        await self.db.flush()

        await self.db.commit()
        return channel

    async def list_for_workspace(self, workspace_id: UUID) -> list[Channel]:
        return await self.repo.list_by_workspace(workspace_id)

    async def get_owned(self, channel_id: UUID, workspace_id: UUID) -> Channel:
        channel = await self.repo.get_by_id(channel_id, workspace_id)
        if channel is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
        return channel

    async def update(self, channel: Channel, payload: ChannelUpdate) -> Channel:
        provider = get_provider(channel.type)

        if payload.credentials:
            merged = {**channel.credentials, **payload.credentials}
            merged = await provider.validate_credentials(merged)
            merged = await provider.setup_webhook(channel.id, merged)
            payload.credentials = merged

        updated_channel = await self.repo.update(channel, payload)
        await self.db.commit()
        return updated_channel

    async def delete(self, channel: Channel) -> None:
        provider = get_provider(channel.type)
        await provider.teardown_webhook(channel.credentials)

        await self.repo.delete(channel)
        await self.db.commit()