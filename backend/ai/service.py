import re
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

    async def generate_audit(
        self,
        metrics: dict[str, Any],
        channel_username: str = "",
        period_days: int = 30,
    ) -> dict[str, Any]:
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
            insight = await self.client.generate_insight(
                metrics,
                channel_username=channel_username,
                period_days=period_days,
            )
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

        sections = _parse_sections(insight)
        recommendations = _extract_recommendations(insight)

        return {
            "status": "ok",
            "summary": sections.get("общая оценка", "AI-аудит сформирован."),
            "strengths": sections.get("сильные стороны", ""),
            "problems": sections.get("проблемные зоны", ""),
            "recommendations": recommendations,
            "best_post_insight": sections.get("лучший пост периода", ""),
            "optimal_time": sections.get("оптимальное время", ""),
            "forecast": sections.get("прогноз", ""),
            "raw_text": insight,
        }


def _parse_sections(text: str) -> dict[str, str]:
    """Разбивает markdown-текст по заголовкам ### на секции."""
    sections: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []

    for line in text.splitlines():
        heading_match = re.match(r"^#{1,3}\s+(.+)", line)
        if heading_match:
            if current_key is not None:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = heading_match.group(1).strip().lower()
            current_lines = []
        elif current_key is not None:
            current_lines.append(line)

    if current_key is not None:
        sections[current_key] = "\n".join(current_lines).strip()

    return sections


def _extract_recommendations(text: str, limit: int = 5) -> list[str]:
    """Извлекает пункты рекомендаций из секции 'Рекомендации'."""
    sections = _parse_sections(text)
    rec_text = sections.get("рекомендации", "")

    if not rec_text:
        # Fallback: ищем по всему тексту.
        rec_text = text

    candidates: list[str] = []
    for line in rec_text.splitlines():
        item = line.strip().lstrip("-• ").strip()
        if not item:
            continue

        # Убираем нумерацию вида "1. ", "2) ", "10. ".
        item = re.sub(r"^\d+[.)]\s*", "", item).strip()

        if item and len(item) > 10:
            candidates.append(item)

    return candidates[:limit]
