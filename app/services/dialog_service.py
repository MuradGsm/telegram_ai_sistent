from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import DialogStatus, MessageSender
from app.models.dialog import Dialog
from app.repositories.dialog_repository import DialogRepository
from app.repositories.workspace_repository import WorkspaceRepository
from app.services.rag_service import rag_service
from app.services.escalation_service import notify_owner_escalation


class DialogService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = DialogRepository(db)
        self.workspace_repo = WorkspaceRepository(db)

    async def handle_incoming_customer_message(
        self, 
        workspace_id: UUID,
        customer_telegram_id: int,
        customer_display_name: str| None,
        text: str
    ) -> tuple[Dialog, str]:
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if workspace is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

        if workspace.messages_used_this_period >= workspace.monthly_message_limit:
            return (
                await self.repo.get_or_create(workspace_id, customer_telegram_id, customer_display_name),
                "Извините, сервис временно недоступен. Мы скоро вернёмся с ответом."
            )

        dialog = await self.repo.get_or_create(
            workspace_id, customer_telegram_id, customer_display_name
        )

        await self.repo.add_message(dialog, MessageSender.CUSTOMER, text)

        if dialog.status in (DialogStatus.ESCALATED, DialogStatus.OPEN_HUMAN):
            return dialog, ''

        answer = await rag_service.answer(str(workspace_id), text)
        await self.repo.add_message(
            dialog,
            MessageSender.BOT,
            answer.content,
            tokens_used=answer.tokens_used,
            confidence_score=answer.confidence,
            source_chunk_ids=[UUID[cid] for cid in answer.source_chunk_ids],
        )

        await self.workspace_repo.increment_message_usage(workspace)

        if answer.needs_escalation:
            await self.repo.set_status(dialog, DialogStatus.ESCALATED)
            await notify_owner_escalation(workspace, dialog, text)

        return dialog, answer.content

    async def owner_reply(self, dialog: Dialog, content: str) -> None:
        await self.repo.add_message(dialog, MessageSender.OWNER, content)
        await self.repo.set_status(dialog, DialogStatus.OPEN_HUMAN)

    async def close(self, dialog: Dialog) -> Dialog:
        return await self.repo.set_status(dialog, DialogStatus.CLOSED)

    async def list_for_workspace(
        self, workspace_id: UUID, status_filter: DialogStatus | None, limit: int, offset: int
    ) -> list[Dialog]:
        return await self.repo.list_by_workspace(workspace_id, status_filter,limit, offset)

    async def get_owned(self, dialog_id: UUID, workspace_id: UUID) -> Dialog:
        dialog = await self.repo.get_by_id(dialog_id)

        if dialog is None or dialog.workspace_id != workspace_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dialog not found")
        return dialog