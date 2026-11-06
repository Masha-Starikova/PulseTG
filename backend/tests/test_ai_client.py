from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import openai
import pytest

from backend.ai.client import AIClient, AIClientError

REQUEST = httpx.Request("POST", "https://api.openai.test/v1/chat/completions")


def status_error(error_class: type[openai.APIStatusError], status_code: int) -> openai.APIStatusError:
    response = httpx.Response(status_code, request=REQUEST)
    return error_class("provider error", response=response, body=None)


def completion(content: str | None) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


@pytest.fixture
def ai_client() -> AIClient:
    client = AIClient(api_key="test-key", model="test-model")
    client.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock()))
    )
    return client


def mocked_create(client: AIClient) -> AsyncMock:
    return client.client.chat.completions.create


def test_missing_api_key_is_reported_on_creation() -> None:
    with pytest.raises(AIClientError, match="OPENAI_API_KEY"):
        AIClient()


async def test_returns_stripped_model_answer(ai_client: AIClient) -> None:
    mocked_create(ai_client).return_value = completion("  текст отчёта \n")

    assert await ai_client.generate_insight({"a": 1}) == "текст отчёта"


async def test_sends_metrics_channel_and_period_to_model(ai_client: AIClient) -> None:
    mocked_create(ai_client).return_value = completion("ok")

    await ai_client.generate_insight({"avg_er": 4.25}, channel_username="durov", period_days=14)

    kwargs = mocked_create(ai_client).await_args.kwargs
    prompt = kwargs["messages"][-1]["content"]
    assert kwargs["model"] == "test-model"
    assert "@durov" in prompt
    assert "14 дней" in prompt
    assert "4.25" in prompt


@pytest.mark.parametrize(
    ("error", "expected_message"),
    [
        (status_error(openai.AuthenticationError, 401), "аутентификации"),
        (status_error(openai.RateLimitError, 429), "лимит"),
        (status_error(openai.BadRequestError, 400), "Некорректный запрос"),
        (openai.APIConnectionError(request=REQUEST), "соединения"),
        (openai.APITimeoutError(request=REQUEST), "соединения"),
        (status_error(openai.InternalServerError, 500), "статус 500"),
        (RuntimeError("неожиданный сбой"), "Непредвиденная"),
    ],
    ids=["auth", "rate-limit", "bad-request", "connection", "timeout", "api-status", "unexpected"],
)
async def test_provider_errors_become_ai_client_error(
    ai_client: AIClient,
    error: Exception,
    expected_message: str,
) -> None:
    mocked_create(ai_client).side_effect = error

    with pytest.raises(AIClientError, match=expected_message) as exc_info:
        await ai_client.generate_insight({})

    assert exc_info.value.__cause__ is error


async def test_provider_details_do_not_reach_error_message(ai_client: AIClient) -> None:
    response = httpx.Response(400, request=REQUEST)
    mocked_create(ai_client).side_effect = openai.BadRequestError(
        "internal prompt dump", response=response, body=None
    )

    with pytest.raises(AIClientError) as exc_info:
        await ai_client.generate_insight({})

    assert "internal prompt dump" not in str(exc_info.value)


@pytest.mark.parametrize(
    "response",
    [completion(""), completion("   \n"), completion(None), SimpleNamespace(choices=[])],
    ids=["empty", "whitespace", "none", "no-choices"],
)
async def test_empty_answer_becomes_ai_client_error(ai_client: AIClient, response: SimpleNamespace) -> None:
    mocked_create(ai_client).return_value = response

    with pytest.raises(AIClientError, match="пустой ответ"):
        await ai_client.generate_insight({})
