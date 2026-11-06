from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.ai.client import AIClientError, AIResponseFormatError
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
    assert len(report["strengths"]) == 2
    assert report["strengths"][0].startswith("ER лучших постов")
    assert report["problems"][0].startswith("Всего 0.5 поста")
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


def without_section(heading: str) -> str:
    """Текст отчёта, из которого вырезана секция вместе с содержимым."""
    start = VALID_REPORT_TEXT.index(f"### {heading}")
    next_heading = VALID_REPORT_TEXT.find("### ", start + 4)
    end = next_heading if next_heading != -1 else len(VALID_REPORT_TEXT)
    return VALID_REPORT_TEXT[:start] + VALID_REPORT_TEXT[end:]


class TestStructureValidation:
    @pytest.mark.parametrize(
        "heading",
        [
            "Общая оценка",
            "Сильные стороны",
            "Проблемные зоны",
            "Рекомендации",
            "Лучший пост периода",
            "Оптимальное время",
            "Прогноз",
        ],
    )
    async def test_missing_section_triggers_one_retry_that_names_it(self, heading: str) -> None:
        service, generate = service_with_answers(without_section(heading), VALID_REPORT_TEXT)

        report = await service.generate_audit({})

        assert report["status"] == "ok"
        assert generate.await_count == 2
        assert generate.await_args_list[0].kwargs.get("correction") is None
        assert heading in generate.await_args_list[1].kwargs["correction"]

    @pytest.mark.parametrize(
        "broken",
        [
            "Просто текст без заголовков",
            VALID_REPORT_TEXT.replace("5. Просить поделиться постом — репостов станет заметно больше.\n", ""),
            VALID_REPORT_TEXT.replace(
                "- Стабильные 1500 просмотров на пост.\n",
                "",
            ),
            VALID_REPORT_TEXT.replace("Оценка 7 из 10: ER 4.2% при 1500 просмотрах.", ""),
        ],
        ids=["no-headings", "four-recommendations", "one-strength", "empty-section"],
    )
    async def test_second_violation_gives_clear_permanent_error(self, broken: str) -> None:
        service, generate = service_with_answers(broken, broken, VALID_REPORT_TEXT)

        with pytest.raises(AIClientError, match="структур") as exc_info:
            await service.generate_audit({})

        assert generate.await_count == 2
        assert exc_info.value.retryable is False

    async def test_empty_answer_counts_as_violation_and_is_retried_once(self) -> None:
        service, generate = service_with_answers(
            AIResponseFormatError("OpenAI вернул пустой ответ"),
            VALID_REPORT_TEXT,
        )

        report = await service.generate_audit({})

        assert report["status"] == "ok"
        assert generate.await_count == 2

    async def test_provider_error_during_correction_is_not_hidden(self) -> None:
        service, _ = service_with_answers("без структуры", AIClientError("Лимит", retryable=True))

        with pytest.raises(AIClientError, match="Лимит") as exc_info:
            await service.generate_audit({})

        assert exc_info.value.retryable is True

    @pytest.mark.parametrize(
        ("original", "variant"),
        [
            ("### Прогноз", "## Прогноз"),
            ("### Прогноз", "### Прогноз:"),
            ("### Прогноз", "### **Прогноз**"),
            ("### Прогноз", "### 7. Прогноз"),
            ("### Прогноз", "### ПРОГНОЗ"),
        ],
    )
    async def test_cosmetic_heading_differences_are_tolerated(self, original: str, variant: str) -> None:
        service, generate = service_with_answers(VALID_REPORT_TEXT.replace(original, variant))

        report = await service.generate_audit({})

        assert report["forecast"].startswith("При текущей динамике")
        assert generate.await_count == 1

    async def test_list_markers_of_any_kind_are_parsed(self) -> None:
        text = VALID_REPORT_TEXT.replace("- ER лучших", "• ER лучших").replace("- Стабильные", "* Стабильные")
        service, _ = service_with_answers(text.replace("1. Публиковать", "1) Публиковать"))

        report = await service.generate_audit({})

        assert report["strengths"][1].startswith("Стабильные")
        assert report["recommendations"][0].startswith("Публиковать")
