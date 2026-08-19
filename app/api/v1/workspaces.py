from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.workspace import (
    WorkspaceConnectBot,
    WorkspaceCreate,
    WorkspaceOut,
    WorkspaceUpdate,
)
from app.services.workspace_service import WorkspaceService


router = APIRouter(prefix='/workspace', tags=['workspace'])

def get_workspace_service(db: AsyncSession = Depends(get_db)) -> WorkspaceService:
    return WorkspaceService(db)


@router.post("", response_model=WorkspaceOut, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    payload: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service)
):
    return await service.create(current_user.id, payload)


@router.get("", response_model=list[WorkspaceOut])
async def list_workspace(
    current_user: User = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service)
):
    return await service.list_for_owner(current_user.id)


@router.get('/{workspace_id}', response_model=WorkspaceOut)
async def get_workspace(
    workspace_id: UUID,
    current_user: User = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service)
):
    return await service.get_owned(workspace_id, current_user.id)


@router.patch('/{workspace_id}', response_model=WorkspaceOut)
async def update_workspace(
    workspace_id: UUID,
    payload: WorkspaceUpdate,
    current_user: User = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service)
):
    workspace = await service.get_owned(workspace_id, current_user.id)
    return await service .update(workspace, payload)


@router.post("/{workspace_id}/connect-bot", response_model=WorkspaceOut)
async def connect_telegram_bot(
    workspace_id: UUID,
    payload: WorkspaceConnectBot,
    current_user: User = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service)
):
    workspace = await service.get_owned(workspace_id, current_user.id)
    return await service.connect_telegram_bot(workspace, payload)


@router.delete('/{workspace_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    workspace_id: UUID,
    current_user: User = Depends(get_current_user),
    service: WorkspaceService = Depends(get_workspace_service)
):
    workspace = await service.get_owned(workspace_id, current_user.id)
    await service.delete(workspace)