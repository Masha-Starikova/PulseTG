import logging
from typing import Any

from backend.ai.client import AIClient, AIClientError, AIResponseFormatError
from backend.ai.report import parse_report
from backend.core.config import settings

logger = logging.getLogger(__name__)

# Первая попытка и один повтор с указанием, что исправить.
MAX_FORMAT_ATTEMPTS = 2


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
        """Возвращает AI-аудит, проверенный по обязательной структуре.

        Сбой AI не маскируется заглушкой: AIClientError уходит наверх,
        иначе неудачный аудит выглядел бы для пользователя как успешный.
        """

        if self.client is None:
            raise AIClientError("AI-анализ недоступен: OPENAI_API_KEY не задан")

        correction: str | None = None
        for attempt in range(1, MAX_FORMAT_ATTEMPTS + 1):
            try:
                insight = await self.client.generate_insight(
                    metrics,
                    channel_username=channel_username,
                    period_days=period_days,
                    correction=correction,
                )
                report = parse_report(insight)
            except AIResponseFormatError as exc:
                logger.warning("AI-отчёт отклонён, попытка %s: %s", attempt, exc)
                correction = str(exc)
                continue

            return {"status": "ok", **report.model_dump(), "raw_text": insight}

        raise AIClientError("AI вернул отчёт не по заданной структуре. Повторите аудит позже.")
