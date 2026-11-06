from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.ai.client import AIClientError
from backend.ai.service import AIInsightsService
from backend.tests.factories import VALID_REPORT_TEXT


def service_with_answers(*answers: str | Exception) -> tuple[AIInsightsService, AsyncMock]:
    client = MagicMock()
    client.generate_insight = AsyncMock(side_effect=list(answers))
    return AIInsightsService(client=client), client.generate_insight


async def test_missing_api_key_is_an_error_not_a_report() -> None:
    with pytest.raises(AIClientError, match="OPENAI_API_KEY"):
        await AIInsightsService().generate_audit({})


async def test_provider_error_is_passed_to_caller() -> None:
    service, _ = service_with_answers(AIClientError("Превышен лимит OpenAI API"))

    with pytest.raises(AIClientError, match="лимит"):
        await service.generate_audit({})


async def test_report_is_split_into_sections() -> None:
    service, _ = service_with_answers(VALID_REPORT_TEXT)

    report = await service.generate_audit({"a": 1}, channel_username="channel", period_days=14)

    assert report["status"] == "ok"
    assert report["summary"].startswith("Оценка 7 из 10")
    assert "ER лучших постов" in report["strengths"]
    assert "0.5 поста в день" in report["problems"]
    assert report["best_post_insight"].startswith("Разбор кейса")
    assert report["optimal_time"].startswith("Вторник")
    assert report["forecast"].startswith("При текущей динамике")
    assert report["raw_text"] == VALID_REPORT_TEXT


async def test_recommendations_lose_numbering_and_keep_order() -> None:
    service, _ = service_with_answers(VALID_REPORT_TEXT)

    recommendations = (await service.generate_audit({}))["recommendations"]

    assert len(recommendations) == 5
    assert recommendations[0].startswith("Публиковать 1 пост в день")
    assert recommendations[4].startswith("Просить поделиться")
