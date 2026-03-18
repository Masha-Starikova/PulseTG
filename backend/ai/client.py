import json
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    RateLimitError,
)

from backend.core.config import settings


class AIClientError(RuntimeError):
    """Ошибки при работе с OpenAI API."""


class AIClient:
    """Низкоуровневый клиент для генерации инсайтов через OpenAI."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        resolved_api_key = api_key or settings.openai_api_key
        if not resolved_api_key:
            raise AIClientError("OPENAI_API_KEY не задан в .env")

        self.model = model or settings.openai_model
        self.client = AsyncOpenAI(
            api_key=resolved_api_key,
            timeout=timeout_seconds or settings.openai_timeout_seconds,
        )

    async def generate_insight(self, structured_data: dict[str, Any]) -> str:
        """Генерирует текстовый инсайт по структурированным метрикам."""

        payload = json.dumps(structured_data, ensure_ascii=False, indent=2)
        prompt = (
            "Ты senior-аналитик Telegram-каналов. "
            "Сформируй краткий аудит и actionable-рекомендации на русском языке. "
            "Ответ структурируй так: 1) Краткий вывод, 2) Сильные стороны, "
            "3) Риски, 4) 3-5 конкретных рекомендаций.\n\n"
            f"Входные данные:\n{payload}"
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Отвечай деловым и конкретным стилем."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
        except AuthenticationError as exc:
            raise AIClientError("Ошибка аутентификации OpenAI: проверьте OPENAI_API_KEY") from exc
        except RateLimitError as exc:
            raise AIClientError("Превышен лимит OpenAI API (Rate Limit)") from exc
        except BadRequestError as exc:
            raise AIClientError(f"Некорректный запрос к OpenAI API: {exc}") from exc
        except APIConnectionError as exc:
            raise AIClientError("Ошибка сетевого соединения с OpenAI API") from exc
        except APIStatusError as exc:
            raise AIClientError(f"OpenAI API вернул статус {exc.status_code}") from exc
        except Exception as exc:
            raise AIClientError("Непредвиденная ошибка при обращении к OpenAI API") from exc

        content = response.choices[0].message.content if response.choices else None
        insight = (content or "").strip()
        if not insight:
            raise AIClientError("OpenAI вернул пустой ответ")

        return insight
