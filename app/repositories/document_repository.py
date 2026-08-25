from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import DocumentStatus
from app.models.document import Document

class DocumentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, document_id: UUID) -> Document | None:
        result = await self.db.execute(select(Document).where(Document.id == document_id))
        return result.scalar_one_or_none()

    async def list_by_workspace(self, workspace_id: UUID) -> list[Document]:
        result = await self.db.execute(
            select(Document)
            .where(Document.workspace_id == workspace_id)
            .order_by(Document.created_at.desc())
        )
        return list(result.scalars().all())

    async def create(
        self, workspace_id: UUID, file_name: str, r2_object_key: str, content_type: str
    ) -> Document:
        document = Document(
            workspace_id = workspace_id,
            file_name = file_name,
            r2_object_key = r2_object_key,
            content_type = content_type,
            status = DocumentStatus.UPLOADED
        )

        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)
        return document

    async def update_status(
        self,
        document: Document, 
        status: DocumentStatus, 
        chunk_count: int | None = None,
        error_message: str | None = None,
    ) -> Document:
        document.status = status
        if chunk_count is not None:
            document.chunk_count = chunk_count
        if error_message is not None:
            document.error_message = error_message
        await self.db.commit()
        await self.db.refresh(document)
        return document

    async def delete(self, document: Document) -> None:
        await self.db.delete(document)
        await self.db.commit()