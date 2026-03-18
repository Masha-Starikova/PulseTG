from typing import Any

from backend.ai.client import AIClient, AIClientError
from backend.core.config import settings


class AIInsightsService:
    """Сервис генерации AI-аудита поверх низкоуровневого AI-клиента."""

    def __init__(self, client: AIClient | None = None) -> None:
        self.client = client

        # Если клиент не передан извне, создаем его только при наличии ключа.
        if self.client is None and settings.openai_api_key:
            self.client = AIClient()

    async def generate_audit(self, metrics: dict[str, Any]) -> dict[str, Any]:
        """Возвращает структурированный AI-аудит по переданным метрикам."""

        if self.client is None:
            return {
                "status": "fallback",
                "summary": "AI-аудит недоступен: OPENAI_API_KEY не задан.",
                "recommendations": [
                    "Проверьте настройку OPENAI_API_KEY в .env.",
                    "Проведите первичную валидацию метрик вручную.",
                    "Повторите запуск аудита после настройки AI-провайдера.",
                ],
                "raw_text": "",
            }

        try:
            insight = await self.client.generate_insight(metrics)
        except AIClientError as exc:
            return {
                "status": "fallback",
                "summary": "AI-аудит завершился с ошибкой внешнего провайдера.",
                "recommendations": [
                    "Повторите попытку позже.",
                    "Проверьте лимиты и доступность OpenAI API.",
                    "Проверьте корректность входных метрик.",
                ],
                "error": str(exc),
                "raw_text": "",
            }

        recommendations = _extract_recommendations(insight)

        return {
            "status": "ok",
            "summary": insight.splitlines()[0] if insight.splitlines() else "AI-аудит сформирован.",
            "recommendations": recommendations,
            "raw_text": insight,
        }


def _extract_recommendations(text: str, limit: int = 5) -> list[str]:
    """Пытаемся извлечь пункты рекомендаций из текста ответа модели."""

    candidates: list[str] = []
    for line in text.splitlines():
        item = line.strip().lstrip("-• ").strip()
        if not item:
            continue

        # Убираем нумерацию вида "1. " или "2) ".
        if len(item) > 2 and item[0].isdigit() and item[1] in {".", ")"}:
            item = item[2:].strip()

        if item:
            candidates.append(item)

    # Возвращаем ограниченное количество пунктов, чтобы ответ был компактным.
    return candidates[:limit]
