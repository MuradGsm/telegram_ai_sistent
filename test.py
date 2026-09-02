import asyncio
import time
from openai import AsyncOpenAI

# Вставь сюда твой NVIDIA API ключ (начинается на nvapi-...)
NVIDIA_API_KEY = "nvapi-YOUR_KEY_HERE"

# Модель для проверки
MODEL_NAME = "meta/llama-3.2-11b-vision-instruct"

client = AsyncOpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key="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",
)


async def test_speed():
    print(f"🔄 Отправка запроса к модели {MODEL_NAME}...")

    start_time = time.perf_counter()

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": "Ты — ассистент поддержки. Отвечай кратко.",
                },
                {
                    "role": "user",
                    "content": "Привет! Расскажи в двух предложениях, как работает RAG.",
                },
            ],
            temperature=0.2,
            max_tokens=200,
        )

        elapsed_time = time.perf_counter() - start_time
        answer = response.choices[0].message.content

        print("\n✅ Ответ получен успешно!")
        print(f"⏱ Время ответа: {elapsed_time:.2f} сек.")
        print("-" * 40)
        print(f"Ответ:\n{answer}")
        print("-" * 40)

    except Exception as e:
        print(f"\n❌ Ошибка вызова API: {e}")


if __name__ == "__main__":
    asyncio.run(test_speed())