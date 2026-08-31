import uuid

from qdrant_client import AsyncQdrantClient, models

from app.core.conf import settings

EMBEDDING_SIZE = 384


class QdrantRepository:

    def __init__(self):
        self._client = AsyncQdrantClient(url=settings.qdrant_url)

    @staticmethod
    def _collection_name(workspace_id: str) -> str:
        return f"workspace_{workspace_id}"

    async def ensure_collection(self, workspace_id: str) -> None:
        name = self._collection_name(workspace_id)
        exists = await self._client.collection_exists(name)
        if not exists:
            await self._client.create_collection(
                collection_name=name,
                vectors_config=models.VectorParams(
                    size=EMBEDDING_SIZE, distance=models.Distance.COSINE
                ),
            )

    async def upsert_chunks(
        self,
        workspace_id: str,
        document_id: str,
        chunks: list[str],
        embeddings: list[list[float]],
    ) -> list[str]:
        await self.ensure_collection(workspace_id)
        name = self._collection_name(workspace_id)

        chunk_ids = [str(uuid.uuid4()) for _ in chunks]
        points = [
            models.PointStruct(
                id=chunk_id,
                vector=vector,
                payload={"document_id": document_id, "text": chunk_text},
            )
            for chunk_id, chunk_text, vector in zip(chunk_ids, chunks, embeddings)
        ]

        await self._client.upsert(collection_name=name, points=points)
        return chunk_ids

    async def delete_by_document(self, workspace_id: str, document_id: str) -> None:
        name = self._collection_name(workspace_id)
        exists = await self._client.collection_exists(name)
        if not exists:
            return

        await self._client.delete(
            collection_name=name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id", match=models.MatchValue(value=document_id)
                        )
                    ]
                )
            ),
        )

    async def search(
        self, workspace_id: str, query_vector: list[float], limit: int = 5
    ) -> list[dict]:
        name = self._collection_name(workspace_id)
        exists = await self._client.collection_exists(name)
        if not exists:
            return []

        # Включаем явную загрузку payload через with_payload=True
        results = await self._client.query_points(
            collection_name=name,
            query=query_vector,
            limit=limit,
            with_payload=True,
        )

        output = []
        for point in results.points:
            payload = point.payload or {}
            output.append({
                "id": str(point.id),
                "text": payload.get("text", ""),
                "score": point.score,
            })

        return output


qdrant_repository = QdrantRepository()