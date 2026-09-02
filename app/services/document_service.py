import uuid
from uuid import UUID

from arq import ArqRedis, create_pool
from arq.connections import RedisSettings
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.conf import settings
from app.external.r2_client import r2_client
from app.models.document import Document
from app.repositories.document_repository import DocumentRepository

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024

_arq_redis_pool: ArqRedis | None = None


async def get_arq_redis() -> ArqRedis:
    global _arq_redis_pool
    if _arq_redis_pool is None:
        _arq_redis_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    return _arq_redis_pool


class DocumentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = DocumentRepository(db)

    async def upload(self, workspace_id: UUID, file: UploadFile) -> Document:
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {file.content_type}",
            )

        file_bytes = await file.read()
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File is too large (max 20MB)",
            )

        safe_filename = file.filename or "file"
        object_key = f"{workspace_id}/{uuid.uuid4()}_{safe_filename}"
        await r2_client.upload_file(object_key, file_bytes, file.content_type)

        document = await self.repo.create(
            workspace_id=workspace_id,
            file_name=safe_filename,
            r2_object_key=object_key,
            content_type=file.content_type or "application/octet-stream",
        )

        # Сначала фиксируем документ в БД, затем отправляем в очередь
        await self.db.commit()
        await self._enqueue_indexing(document.id)
        return document

    async def list_for_workspace(self, workspace_id: UUID) -> list[Document]:
        return await self.repo.list_by_workspace(workspace_id)

    async def get_owned(self, document_id: UUID, workspace_id: UUID) -> Document:
        document = await self.repo.get_by_id(document_id, workspace_id)
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
            )
        return document

    async def delete(self, document: Document) -> None:
        await r2_client.delete_file(document.r2_object_key)
        await self.repo.delete(document)
        await self.db.commit()

    @staticmethod
    async def _enqueue_indexing(document_id: UUID) -> None:
        redis = await get_arq_redis()
        await redis.enqueue_job("process_document", str(document_id))