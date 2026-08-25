from uuid import UUID

from arq.connections import RedisSettings

from app.core.conf import settings
from app.core.enums import DocumentStatus
from app.db.session import AsyncSessionLocal
from app.external.qdrant_repository import qdrant_repository
from app.external.r2_client import r2_client
from app.repositories.document_repository import DocumentRepository
from app.services.text_extraction import extract_text, split_into_chunks
from app.services.embedder import embed_texts


async def process_document(ctx: dict, document_id: str) -> None:
    async with AsyncSessionLocal() as db:
        repo = DocumentRepository(db)
        document = await repo.get_by_id(UUID(document_id))
        if document is None:
            return

        try:
            await repo.update_status(document, DocumentStatus.PROCESSING)

            file_bytes = await r2_client.download_file(document.r2_object_key)
            text = extract_text(file_bytes, document.content_type)
            chunks = split_into_chunks(text)

            if not chunks:
                await repo.update_status(
                    document, DocumentStatus.FAILED, error_message="No extractable text found"
                )
                return

            embeddings = embed_texts(chunks)

            await qdrant_repository.upsert_chunks(
                workspace_id=str(document.workspace_id),
                document_id=str(document.id),
                chunks=chunks,
                embeddings=embeddings,
            )

            await repo.update_status(document, DocumentStatus.INDEXED, chunk_count=len(chunks))
        except Exception as exc:
            await repo.update_status(document, DocumentStatus.FAILED, error_message=str(exc)[:1000])


async def startup(ctx: dict) -> None:
    ctx["ready"] = True


async def shutdown(ctx: dict) -> None:
    pass


class WorkerSettings:
    functions = [process_document]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)