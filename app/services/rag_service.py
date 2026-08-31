from dataclasses import dataclass
import logging

from openai import AsyncOpenAI

from app.core.conf import settings
from app.external.qdrant_repository import qdrant_repository
from app.services.embedder import embed_texts_async

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.45

SYSTEM_PROMPT = (
    "Ты — вежливый и профессиональный онлайн-консультант поддержки клиентов.\n"
    "Твоя главная задача — давать точные и полезные ответы на основе предоставленного контекста.\n\n"
    "СТРОГИЕ ПРАВИЛА ЯЗЫКА И СТИЛЯ:\n"
    "1. ОПРЕДЕЛЕНИЕ ЯЗЫКА: Определи язык вопроса клиента. Твой ответ ДОЛЖЕН БЫТЬ строго на том же языке, на котором написал клиент.\n"
    "   - Если клиент написал на азербайджанском языке — отвечай СТРОГО на азербайджанском (Azerbaijani language).\n"
    "   - Если клиент написал на русском языке — отвечай СТРОГО на русском.\n"
    "2. Отвечай ТОЛЬКО на основе предоставленного контекста. Не придумывай факты.\n"
    "3. Пиши кратко, вежливо и естественным языком.\n"
    "4. Если в контексте нет ответа на вопрос, вежливо ответь на языке клиента, что передаешь запрос специалисту."
)

_llm_client = AsyncOpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=settings.llm_api_key,
)


@dataclass
class RagAnswer:
    content: str
    confidence: float
    source_chunk_ids: list[str]
    tokens_used: int

    @property
    def needs_escalation(self) -> bool:
        return self.confidence < CONFIDENCE_THRESHOLD


class RagService:
    async def answer(self, workspace_id: str, question: str) -> RagAnswer:
        # 1. Асинхронное получение векторного эмбеддинга
        query_vectors = await embed_texts_async([question])
        query_vector = query_vectors[0]

        # 2. Поиск ближайших чанков в Qdrant
        matches = await qdrant_repository.search(workspace_id, query_vector, limit=5)

        logger.info(
            f"=== QDRANT SEARCH | Workspace: {workspace_id} | Matches: {len(matches)} ==="
        )

        top_score = matches[0].get("score", 0.0) if matches else 0.0

        if matches:
            logger.info(
                f"Top Score: {top_score} (Threshold: {CONFIDENCE_THRESHOLD})"
            )
            logger.info(f"Top Match Sample: {matches[0]}")

        # 3. Эскалация: если контекста нет или score ниже порога
        if not matches or top_score < CONFIDENCE_THRESHOLD:
            logger.info(
                f"Escalating: matches empty or score {top_score} < {CONFIDENCE_THRESHOLD}"
            )

            # Динамический ответ на языке клиента при переводе на оператора
            fallback_completion = await _llm_client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Сообщение клиента: {question}\n\n"
                            "Контекст пуст. Вежливо ответь клиенту НА ЕГО ЯЗЫКЕ, "
                            "что ты переводишь запрос на оператора и попроси немного подождать."
                        ),
                    },
                ],
                temperature=0.1,
                max_tokens=150,
            )

            fallback_text = (
                fallback_completion.choices[0].message.content
                or "Müraciətiniz оператора yönləndirildi, zəhmət olmasa gözləyin."
            )

            return RagAnswer(
                content=fallback_text,
                confidence=top_score,
                source_chunk_ids=[match["id"] for match in matches] if matches else [],
                tokens_used=0,
            )

        context = "\n\n".join(match.get("text", "") for match in matches)

        # 4. Генерация основного ответа через LLM
        completion = await _llm_client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Контекст из базы знаний:\n{context}\n\nВопрос клиента: {question}",
                },
            ],
            temperature=0.2,
            top_p=0.7,
            max_tokens=512,
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