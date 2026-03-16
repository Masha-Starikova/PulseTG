from dataclasses import dataclass

from openai import AsyncOpenAI

from backend.core.config import settings


@dataclass(slots=True)
class AIInsightsService:
    """Генерация практических рекомендаций по результатам аналитики."""

    model: str = settings.openai_model

    def __post_init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.openai_timeout_seconds,
        )

    async def generate_recommendations(self, metrics: dict) -> dict:
        # Возвращаем детерминированный fallback, если AI-ключ не задан.
        if not settings.openai_api_key:
            return {
                "summary": "AI-ключ не настроен, сгенерирован базовый отчет.",
                "recommendations": [
                    "Увеличьте частоту публикаций в прайм-тайм вашей аудитории.",
                    "Добавьте в контент-план больше интерактивных постов.",
                    "Тестируйте форматы с высоким retention и сохраняйте лучшие практики.",
                ],
            }

        prompt = (
            "Ты аналитик Telegram-каналов. "
            "На основе метрик верни краткий вывод и 3 рекомендации. "
            f"Метрики: {metrics}"
        )

        response = await self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "Отвечай по-русски в деловом стиле."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )

        content = response.choices[0].message.content or ""
        recommendations = [line.strip("- ").strip() for line in content.splitlines() if line.strip()]

        return {
            "summary": recommendations[0] if recommendations else "Отчет сформирован.",
            "recommendations": recommendations[1:4] if len(recommendations) > 1 else [],
            "raw_text": content,
        }
