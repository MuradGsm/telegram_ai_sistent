from uuid import UUID

from arq.connections import RedisSettings
from fastembed import TextEmbedding

from app.core.conf import settings
from app.core.enums import DocumentStatus
from app.db.session import AsyncSessionLocal
from app.external.qdrant_repository import qdrant_repository
from app.external.r2_client import r2_client
from app.repositories.document_repository import DocumentRepository
from app.services.text_extraction import extract_text, split_into_chunks

_embedding_model: TextEmbedding | None = None


def get_embedding_model() -> TextEmbedding:
    global _embedding_model

    if _embedding_model is None:
        _embedding_model = TextEmbedding(model_name='BAAI/bge-small-en-v1.5')

    return _embedding_model

async def process_document(ctx: dict, document_id: str) -> None:
    async with  AsyncSessionLocal() as db:
        repo = DocumentRepository(db)
        document = await repo.get_by_id(document_id)
        if document is None:
            return

        try:
            await repo.update_status(document, DocumentStatus.PROCESSING)

            file_bytes = await r2_client.download_file(document.r2_object_key)
            text = extract_text(file_bytes, document.content_type)
            chunks = split_into_chunks(text)

            if not chunks:
                await repo.update_status (
                    document, DocumentStatus.FAILED, error_message="No extractable text found"
                )
                return

            model = get_embedding_model
            embeddings = list(model.embd(chunks))
            embeddings = [vector.tolist() for vector in embeddings]

            await qdrant_repository.upsert_chunks(
                workspace_id=(document.workspace_id),
                document_id=str(document.id),
                chunks=chunks,
                embeddings=embeddings
            )

            await repo.update_status(document, DocumentStatus.INDEXED, chunk_count=len(chunks))
        except Exception as exc:
            await repo.update_status(document, DocumentStatus.FAILED, error_message=str(exc)[:1000] )


async def startup(ctx: dict) -> None:
    ctx['ready'] = True

async def shutdown(ctx: dict) -> None:
    pass

class WorkspaceSettings:
    functions = [process_document]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)