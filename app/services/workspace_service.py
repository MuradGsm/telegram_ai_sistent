from uuid import UUID

import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.conf import settings
from app.models.workspace import Workspace
from app.repositories.workspace_repository import WorkspaceRepository
from app.schemas.workspace import WorkspaceConnectBot, WorkspaceCreate, WorkspaceUpdate


class WorkspaceService:
    def __init__(self, db: AsyncSession):
        self.repo = WorkspaceRepository(db)

    async def create(self, owner_id: UUID, payload: WorkspaceCreate) -> Workspace:
        return await self.repo.create(owner_id, payload)

    async def list_for_owner(self, owner_id: UUID) -> list[Workspace]:
        return await self.repo.list_by_owner(owner_id)

    async def get_owned(self, workspace_id: UUID, owner_id: UUID) -> Workspace:
        workspace = await self.repo.get_by_id(workspace_id)

        if workspace is None or workspace.owner_id != owner_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Workspace not found')
        return workspace

    async def update(self, workspace: Workspace, payload: WorkspaceUpdate) -> Workspace:
        return await self.repo.update(workspace, payload)

    async def connect_telegram_bot(
        self, workspace: Workspace, payload: WorkspaceConnectBot
    ) -> Workspace:
        username = await self._validate_bot_token(payload.telegram_bot_token)
        await self._set_webhook(workspace.id, payload.telegram_bot_token)
        return await self.repo.set_telegram_bot(workspace, payload.telegram_bot_token, username)


    @staticmethod
    async def _validate_bot_token(token: str) -> str:
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.get(f'https://api.telegram.org/bot{token}/getMe')
            except httpx.HTTPError as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not reach Telegram API"
                ) from exc

            data = resp.json()
            if not data.get("ok"):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Telegram bot token")

            return data['result']['username']

    @staticmethod
    async def _set_webhook(workspace_id, token: str) -> None:
        webhook_url = f"{settings.public_base_url}/api/v1/telegram/webhook/{workspace_id}"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{token}/setWebhook",
                json={"url": webhook_url},
            )
        data = resp.json()