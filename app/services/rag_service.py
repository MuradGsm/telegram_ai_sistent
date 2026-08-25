from openai import AsyncOpenAI

from app.core.conf import settings
from app.external.qdrant_repository import qdrant_repository
from app.workers.tasks import get_embedding_model

CONFIDENCE_THRESHOLD = 0.45

SYSTEM_PROMPT = (
    "Ты — ассистент поддержки клиентов бизнеса. Отвечай ТОЛЬКО на основе "
    "предоставленного контекста из документов компании. Если в контексте нет "
    "ответа на вопрос — прямо скажи, что не можешь ответить, и не выдумывай факты."
)

_llm_client = AsyncOpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=settings.llm_api_key
)

class RagAnswer:
    def __init__(self, content: str, confidence: float, source_chunk_ids: list[str], tokens_used: int):
        self.content = content
        self.confidence = confidence
        self.source_chunk_ids = source_chunk_ids
        self.tokens_used = tokens_used

    @property
    def needs_escalation(self) -> bool:
        return self.confidence < CONFIDENCE_THRESHOLD


class RagService:
    async def answer(self, workspace_id: str, question: str) -> RagAnswer:
        query_vector = list(get_embedding_model().embed([question]))[0].tolist()

        matches = await qdrant_repository.search(workspace_id, query_vector, limit=5)

        if not matches:
            return RagAnswer(
                content="Пока не могу ответить на этот вопрос — передаю специалисту.",
                confidence=0.0,
                source_chunk_ids=[],
                tokens_used=0,
            )

        context = "\n\n".join(match['text'] for match in matches)
        top_score = matches[0]['score']

        completion = await _llm_client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Контекст:\n{context}\n\nВопрос клиента: {question}"},
            ],
            temperature=0.2,
            top_p=0.7,
            max_tokens=1024,
        )

        content = completion.choices[0].message.content or ""
        tokens_used = completion.usage.total_tokens if completion.usage else 0

        return RagAnswer(
            content=content,
            confidence=top_score,
            source_chunk_ids=[match["id"] for match in matches],
            tokens_used=tokens_used,
        )

    
rag_service = RagService()