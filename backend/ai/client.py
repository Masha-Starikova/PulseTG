import json
import logging
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
from backend.core.errors import AuditError

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Ты эксперт по аналитике Telegram-каналов с опытом работы с тысячами каналов разных ниш. "
    "Твоя задача — давать конкретный, actionable аудит на основе реальных данных. "
    "Всегда указывай числа из входных данных. Не пиши общих фраз без привязки к метрикам. "
    "Отвечай деловым стилем на русском языке, без воды и клише."
)

USER_PROMPT_TEMPLATE = """\
Проведи аудит Telegram-канала @{channel_username} за последние {period_days} дней.

## ВХОДНЫЕ ДАННЫЕ:
{metrics_json}

## СТРУКТУРА ОТВЕТА (строго соблюдай):

### Общая оценка
Одно предложение: оценка канала от 1 до 10 и её обоснование на основе цифр (ER, просмотры, динамика).

### Сильные стороны
- 2-3 конкретных сильных стороны С ЧИСЛАМИ из данных выше.

### Проблемные зоны
- 2-3 конкретных проблемы С ЧИСЛАМИ. Укажи, как это влияет на рост канала.

### Рекомендации
1. [Конкретное действие] — [ожидаемый результат, основанный на паттерне лучших постов]
2. [Конкретное действие] — [ожидаемый результат]
3. [Конкретное действие] — [ожидаемый результат]
4. [Конкретное действие] — [ожидаемый результат]
5. [Конкретное действие] — [ожидаемый результат]

### Лучший пост периода
Кратко опиши что сработало лучше всего и почему (на основе best_posts из данных).

### Оптимальное время
На основе posting_time из данных: в какие дни и часы лучше публиковать (с числами avg_er).

### Прогноз
Если trends.direction = "growing"/"declining"/"stable" — что произойдёт с каналом через месяц при текущей динамике?
"""


class AIClientError(AuditError):
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

    async def generate_insight(
        self,
        structured_data: dict[str, Any],
        channel_username: str = "",
        period_days: int = 30,
    ) -> str:
        """Генерирует текстовый инсайт по структурированным метрикам."""

        payload = json.dumps(structured_data, ensure_ascii=False, indent=2)
        prompt = USER_PROMPT_TEMPLATE.format(
            channel_username=channel_username,
            period_days=period_days,
            metrics_json=payload,
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
        except AuthenticationError as exc:
            raise AIClientError("Ошибка аутентификации OpenAI: проверьте OPENAI_API_KEY") from exc
        except RateLimitError as exc:
            # Закончившиеся деньги тоже приходят как 429, но повтор тут не поможет.
            raise AIClientError(
                "Превышен лимит OpenAI API (Rate Limit)",
                retryable=exc.code != "insufficient_quota",
            ) from exc
        except BadRequestError as exc:
            # Детали провайдера остаются в логах: error_message видит пользователь.
            logger.warning("OpenAI отклонил запрос: %s", exc)
            raise AIClientError("Некорректный запрос к OpenAI API") from exc
        except APIConnectionError as exc:
            # APITimeoutError наследуется от APIConnectionError, таймауты попадают сюда же.
            raise AIClientError("Ошибка сетевого соединения с OpenAI API", retryable=True) from exc
        except APIStatusError as exc:
            raise AIClientError(
                f"OpenAI API вернул статус {exc.status_code}",
                retryable=exc.status_code >= 500,
            ) from exc
        except Exception as exc:
            raise AIClientError("Непредвиденная ошибка при обращении к OpenAI API") from exc

        content = response.choices[0].message.content if response.choices else None
        insight = (content or "").strip()
        if not insight:
            raise AIClientError("OpenAI вернул пустой ответ")

        return insight
