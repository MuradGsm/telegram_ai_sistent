from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.channel import Channel
from app.models.workspace import Workspace
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate


class WorkspaceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, workspace_id: UUID) -> Workspace | None:
        result = await self.db.execute(select(Workspace).where(Workspace.id == workspace_id))
        return result.scalar_one_or_none()

    async def list_by_owner(self, owner_id: UUID) -> list[Workspace]:
        result = await self.db.execute(
            select(Workspace)
            .where(Workspace.owner_id == owner_id)
            .order_by(Workspace.created_at)
        )
        return list(result.scalars().all())

    async def list_by_owner_with_channel_counts(self, owner_id: UUID) -> list[tuple[Workspace, int]]:
        """Возвращает воркспейсы владельца вместе с количеством подключённых каналов.

        Используется для списка воркспейсов на фронте (active_channels_count).
        """
        result = await self.db.execute(
            select(Workspace, func.count(Channel.id))
            .outerjoin(Channel, Channel.workspace_id == Workspace.id)
            .where(Workspace.owner_id == owner_id)
            .group_by(Workspace.id)
            .order_by(Workspace.created_at)
        )
        return [(row[0], row[1]) for row in result.all()]

    async def create(self, owner_id: UUID, payload: WorkspaceCreate) -> Workspace:
        workspace = Workspace(name=payload.name, timezone=payload.timezone, owner_id=owner_id)
        self.db.add(workspace)
        await self.db.flush()
        return workspace

    async def update(self, workspace: Workspace, payload: WorkspaceUpdate) -> Workspace:
        data = payload.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(workspace, field, value)
        await self.db.flush()
        return workspace

    async def increment_message_usage(self, workspace: Workspace) -> Workspace:
        workspace.messages_used_this_period += 1
        await self.db.flush()
        return workspace

    async def delete(self, workspace: Workspace) -> None:
        await self.db.delete(workspace)
        await self.db.flush()