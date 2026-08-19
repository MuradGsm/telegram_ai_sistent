from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
            select(Workspace).where(Workspace.owner_id == owner_id).order_by(Workspace.created_at)
        )
        return list(result.scalars().all())

    async def create(self, owner_id: UUID, payload: WorkspaceCreate) -> Workspace:
        workspace = Workspace(name=payload.name, timezone=payload.timezone, owner_id=owner_id)
        self.db.add(workspace)
        await self.db.commit()
        await self.db.refresh(workspace)

        return workspace

    async def update(self, workspace: Workspace, payload: WorkspaceUpdate) -> Workspace:
        data = payload.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(workspace, field, value)

        await self.db.commit()
        await self.db.refresh(workspace)

        return workspace

    async def set_telegram_bot(self, workspace: Workspace, token: str, username: str) -> Workspace:
        workspace.telegram_bot_token = token
        workspace.telegram_bot_username = username
        workspace.is_bot_active = True
        await self.db.commit()
        await self.db.refresh(workspace)

        return workspace

    async def delete(self, workspace: Workspace) -> None:
        await self.db.delete(workspace)
        await self.db.commit()