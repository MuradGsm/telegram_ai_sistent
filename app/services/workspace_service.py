from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workspace import Workspace
from app.repositories.workspace_repository import WorkspaceRepository
from app.schemas.workspace import WorkspaceCreate, WorkspaceListOut, WorkspaceUpdate


class WorkspaceService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = WorkspaceRepository(db)

    async def create(self, owner_id: UUID, payload: WorkspaceCreate) -> Workspace:
        workspace = await self.repo.create(owner_id, payload)
        await self.db.commit()
        return workspace

    async def get_owned(self, workspace_id: UUID, owner_id: UUID) -> Workspace:
        workspace = await self.repo.get_by_id(workspace_id)
        if workspace is None or workspace.owner_id != owner_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
            )
        return workspace

    async def list_for_owner(self, owner_id: UUID) -> list[WorkspaceListOut]:
        rows = await self.repo.list_by_owner_with_channel_counts(owner_id)
        result = []
        for workspace, count in rows:
            base = WorkspaceListOut.model_validate(workspace, from_attributes=True)
            base.active_channels_count = count
            result.append(base)
        return result

    async def update(self, workspace: Workspace, payload: WorkspaceUpdate) -> Workspace:
        updated = await self.repo.update(workspace, payload)
        await self.db.commit()
        return updated

    async def delete(self, workspace: Workspace) -> None:
        await self.repo.delete(workspace)
        await self.db.commit()