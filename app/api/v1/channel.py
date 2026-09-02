from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.channel import ChannelCreate, ChannelOut, ChannelUpdate
from app.services.channel_service import ChannelService
from app.services.workspace_service import WorkspaceService

router = APIRouter(tags=["channels"])


@router.post(
    "/workspaces/{workspace_id}/channels",
    response_model=ChannelOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_channel(
    workspace_id: UUID,
    payload: ChannelCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workspace_service = WorkspaceService(db)
    await workspace_service.get_owned(workspace_id, current_user.id)

    channel_service = ChannelService(db)
    return await channel_service.create(workspace_id, payload)


@router.get(
    "/workspaces/{workspace_id}/channels",
    response_model=list[ChannelOut],
)
async def list_channels(
    workspace_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workspace_service = WorkspaceService(db)
    await workspace_service.get_owned(workspace_id, current_user.id)

    channel_service = ChannelService(db)
    return await channel_service.list_for_workspace(workspace_id)


@router.patch(
    "/workspaces/{workspace_id}/channels/{channel_id}",
    response_model=ChannelOut,
)
async def update_channel(
    workspace_id: UUID,
    channel_id: UUID,
    payload: ChannelUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workspace_service = WorkspaceService(db)
    await workspace_service.get_owned(workspace_id, current_user.id)

    channel_service = ChannelService(db)
    channel = await channel_service.get_owned(channel_id, workspace_id)
    return await channel_service.update(channel, payload)


@router.delete(
    "/workspaces/{workspace_id}/channels/{channel_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_channel(
    workspace_id: UUID,
    channel_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workspace_service = WorkspaceService(db)
    await workspace_service.get_owned(workspace_id, current_user.id)

    channel_service = ChannelService(db)
    channel = await channel_service.get_owned(channel_id, workspace_id)
    await channel_service.delete(channel)