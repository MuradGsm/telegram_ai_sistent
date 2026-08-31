from fastapi.concurrency import run_in_threadpool
from fastembed import TextEmbedding

_embedding_model: TextEmbedding | None = None

EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def get_embedding_model() -> TextEmbedding:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = TextEmbedding(model_name=EMBEDDING_MODEL_NAME)
    return _embedding_model


def _embed_texts_sync(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()
    return [vector.tolist() for vector in model.embed(texts)]


async def embed_texts_async(texts: list[str]) -> list[list[float]]:
    """Асинхронная обёртка для безопасного вызова в FastAPI / Asyncio."""
    return await run_in_threadpool(_embed_texts_sync, texts)