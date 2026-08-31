from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import DialogStatus, MessageSender
from app.models.dialog import Dialog
from app.repositories.dialog_repository import DialogRepository
from app.repositories.workspace_repository import WorkspaceRepository
from app.schemas.dialog import MessageOut
from app.services.escalation_service import notify_owner_escalation
from app.services.rag_service import rag_service
from app.ws.manager import ws_manager


class DialogService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = DialogRepository(db)
        self.workspace_repo = WorkspaceRepository(db)

    async def _broadcast_message(self, dialog_id: UUID, message) -> None:
        await ws_manager.broadcast(
            dialog_id,
            {"type": "message", "data": MessageOut.model_validate(message).model_dump(mode="json")},
        )

    async def _broadcast_status(self, dialog_id: UUID, status_: DialogStatus) -> None:
        await ws_manager.broadcast(
            dialog_id,
            {"type": "status", "data": {"status": status_.value}},
        )

    async def handle_incoming_customer_message(
        self,
        workspace_id: UUID,
        customer_telegram_id: int,
        customer_display_name: str | None,
        text: str,
    ) -> tuple[Dialog, str]:
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if workspace is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

        dialog = await self.repo.get_or_create(
            workspace_id, customer_telegram_id, customer_display_name
        )

        if workspace.messages_used_this_period >= workspace.monthly_message_limit:
            msg = await self.repo.add_message(dialog, MessageSender.CUSTOMER, text)
            await self._broadcast_message(dialog.id, msg)
            return (
                dialog,
                "Извините, сервис временно недоступен. Мы скоро вернёмся с ответом.",
            )

        customer_msg = await self.repo.add_message(dialog, MessageSender.CUSTOMER, text)
        await self._broadcast_message(dialog.id, customer_msg)

        if dialog.status in (DialogStatus.ESCALATED, DialogStatus.OPEN_HUMAN):
            return dialog, "Оператор уже подключен к диалогу и скоро вам ответит."

        answer = await rag_service.answer(str(workspace_id), text)
        chunk_uuids = [
            UUID(cid) if isinstance(cid, str) else cid
            for cid in answer.source_chunk_ids
        ]

        bot_msg = await self.repo.add_message(
            dialog,
            MessageSender.BOT,
            answer.content,
            tokens_used=answer.tokens_used,
            confidence_score=answer.confidence,
            source_chunk_ids=chunk_uuids,
        )
        await self._broadcast_message(dialog.id, bot_msg)

        await self.workspace_repo.increment_message_usage(workspace)

        if answer.needs_escalation:
            await self.repo.set_status(dialog, DialogStatus.ESCALATED)
            await self._broadcast_status(dialog.id, DialogStatus.ESCALATED)
            await notify_owner_escalation(workspace, dialog, text)

        return dialog, answer.content

    async def owner_reply(self, dialog: Dialog, content: str) -> None:
        message = await self.repo.add_message(dialog, MessageSender.OWNER, content)
        await self._broadcast_message(dialog.id, message)
        if dialog.status != DialogStatus.OPEN_HUMAN:
            await self.repo.set_status(dialog, DialogStatus.OPEN_HUMAN)
            await self._broadcast_status(dialog.id, DialogStatus.OPEN_HUMAN)

    async def close(self, dialog: Dialog) -> Dialog:
        dialog = await self.repo.set_status(dialog, DialogStatus.CLOSED)
        await self._broadcast_status(dialog.id, DialogStatus.CLOSED)
        return dialog

    async def list_for_workspace(
        self,
        workspace_id: UUID,
        status_filter: DialogStatus | None,
        limit: int,
        offset: int,
    ) -> list[Dialog]:
        return await self.repo.list_by_workspace(
            workspace_id, status_filter, limit, offset
        )

    async def get_owned(self, dialog_id: UUID, workspace_id: UUID) -> Dialog:
        dialog = await self.repo.get_by_id(dialog_id)
        if dialog is None or dialog.workspace_id != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Dialog not found"
            )
        return dialog

    async def get_owned_with_messages(self, dialog_id: UUID, workspace_id: UUID) -> Dialog:
        dialog = await self.repo.get_by_id_with_messages(dialog_id)
        if dialog is None or dialog.workspace_id != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Dialog not found"
            )
        return dialog