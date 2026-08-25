from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import DialogStatus, MessageSender
from app.models.dialog import Dialog, Message


class DialogRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, dialog_id: UUID) -> Dialog | None:
        result = await self.db.execute(select(Dialog).where(Dialog.id == dialog_id))
        return result.scalar_one_or_none()

    async def get_or_create(
        self, workspace_id: UUID, customer_telegram_id: int, customer_display_name: str | None
    ) -> Dialog:
        result = await self.db.execute(
            select(Dialog).where(
                Dialog.workspace_id == workspace_id,
                Dialog.customer_telegram_id == customer_telegram_id,
                Dialog.status != DialogStatus.CLOSED
            )
        )
        dialog = result.scalar_one_or_none()
        if dialog is not None:
            return dialog

        dialog = Dialog(
            workspace_id=workspace_id,
            customer_telegram_id=customer_telegram_id,
            customer_display_name=customer_display_name,
            status=DialogStatus.OPEN_AUTO,
        )

        self.db.add(dialog)
        await self.db.commit()
        await self.db.refresh(dialog)
        return dialog

    async def list_by_workspace(
        self, workspace_id: UUID, status: DialogStatus | None, limit: int, offset: int
    ) -> list[Dialog]:
        query = select(Dialog).where(Dialog.workspace_id == workspace_id)
        if status is not None:
            query = query.where(Dialog.status == status)

        query = query.order_by(Dialog.updated_at.desc()).limit(limit).offset(offset)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def set_status(self, dialog: Dialog, status: DialogStatus) -> Dialog:
        dialog.status = status
        await self.db.commit()
        await self.db.refresh(dialog)
        return dialog

    async def add_message(
        self,
        dialog: Dialog,
        sender: MessageSender,
        content: str,
        tokens_used: int | None = None,
        confidence_score: float | None = None,
        source_chunk_ids: list[UUID] | None = None,
    ) -> Message:
        message = Message(
            dialog_id=dialog.id,
            sender=sender,
            content=content,
            tokens_used=tokens_used,
            confidence_score=confidence_score,
            source_chunk_ids=source_chunk_ids,
        )
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        return message