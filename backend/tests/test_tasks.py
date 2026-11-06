import asyncio
from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from celery.result import EagerResult
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.ai.client import AIClientError
from backend.ai.service import AIInsightsService
from backend.models import AuditRequest, AuditStatus
from backend.services import tasks
from backend.services.tasks import retry_countdown, run_channel_audit
from backend.telegram.telegram_collector import TelegramCollectorError
from backend.tests.factories import VALID_REPORT_TEXT

pytestmark = pytest.mark.integration

POSTS = [{"id": 1, "date": "2026-03-02T10:00:00+00:00", "text": "пост", "views": 100, "reactions": 5}]
ATTEMPTS_TOTAL = run_channel_audit.max_retries + 1


def transient() -> TelegramCollectorError:
    return TelegramCollectorError("Сеть недоступна", retryable=True)


@pytest.fixture
def collector(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock = AsyncMock(return_value=POSTS)
    monkeypatch.setattr("backend.services.audit_service.get_channel_posts", mock)
    return mock


@pytest.fixture
def ai_answer(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    ai_client = MagicMock()
    ai_client.generate_insight = AsyncMock(return_value=VALID_REPORT_TEXT)
    monkeypatch.setattr(
        "backend.services.audit_service.AIInsightsService",
        lambda: AIInsightsService(client=ai_client),
    )
    return ai_client.generate_insight


@pytest.fixture
async def audit_id(session_factory: async_sessionmaker[AsyncSession]) -> UUID:
    async with session_factory() as session:
        audit = AuditRequest(channel_username="channel", status=AuditStatus.pending)
        session.add(audit)
        await session.commit()
        return audit.id


@pytest.fixture
def stored(session_factory: async_sessionmaker[AsyncSession]) -> Callable:
    async def read(audit_id: UUID) -> AuditRequest:
        async with session_factory() as session:
            return await session.get(AuditRequest, audit_id)

    return read


async def run_task(audit_id: UUID | str) -> EagerResult:
    # apply() выполняет задачу и её повторы синхронно, как воркер, но без брокера.
    # Отдельный поток: задаче нужен свой event loop, как в настоящем воркере.
    return await asyncio.to_thread(run_channel_audit.apply, args=[str(audit_id)])


async def test_success_saves_report(
    audit_id: UUID,
    stored: Callable,
    collector: AsyncMock,
    ai_answer: AsyncMock,
) -> None:
    result = await run_task(audit_id)

    assert result.successful()
    assert result.result == {"audit_id": str(audit_id), "status": "completed"}
    audit = await stored(audit_id)
    assert audit.status is AuditStatus.completed
    assert audit.report["ai"]["status"] == "ok"
    collector.assert_awaited_once()


async def test_transient_error_is_retried_until_success(
    audit_id: UUID,
    stored: Callable,
    collector: AsyncMock,
    ai_answer: AsyncMock,
) -> None:
    collector.side_effect = [transient(), transient(), POSTS]

    await run_task(audit_id)

    audit = await stored(audit_id)
    assert collector.await_count == 3
    assert audit.status is AuditStatus.completed
    assert audit.error_message is None


async def test_transient_ai_error_is_retried(
    audit_id: UUID,
    stored: Callable,
    collector: AsyncMock,
    ai_answer: AsyncMock,
) -> None:
    ai_answer.side_effect = [AIClientError("Лимит", retryable=True), VALID_REPORT_TEXT]

    await run_task(audit_id)

    assert (await stored(audit_id)).status is AuditStatus.completed
    assert ai_answer.await_count == 2


async def test_failed_is_set_only_after_retries_are_exhausted(
    audit_id: UUID,
    stored: Callable,
    collector: AsyncMock,
    ai_answer: AsyncMock,
) -> None:
    seen_statuses: list[AuditStatus] = []

    async def collect(*_args: object, **_kwargs: object) -> list[dict]:
        seen_statuses.append((await stored(audit_id)).status)
        raise transient()

    collector.side_effect = collect

    result = await run_task(audit_id)

    assert result.failed()
    assert seen_statuses == [AuditStatus.running] * ATTEMPTS_TOTAL
    audit = await stored(audit_id)
    assert audit.status is AuditStatus.failed
    assert audit.error_message == "Сеть недоступна"
    assert audit.report is None


@pytest.mark.parametrize(
    ("step", "error"),
    [
        ("collector", TelegramCollectorError("Канал не найден")),
        ("ai_answer", AIClientError("Ошибка аутентификации OpenAI")),
    ],
    ids=["channel-not-found", "ai-auth"],
)
async def test_permanent_error_fails_on_first_attempt(
    audit_id: UUID,
    stored: Callable,
    collector: AsyncMock,
    ai_answer: AsyncMock,
    step: str,
    error: Exception,
) -> None:
    {"collector": collector, "ai_answer": ai_answer}[step].side_effect = error

    await run_task(audit_id)

    audit = await stored(audit_id)
    assert collector.await_count == 1
    assert audit.status is AuditStatus.failed
    assert audit.error_message == str(error)


async def test_unexpected_error_fails_without_exposing_details(
    audit_id: UUID,
    stored: Callable,
    collector: AsyncMock,
    ai_answer: AsyncMock,
) -> None:
    collector.side_effect = KeyError("internal_field")

    await run_task(audit_id)

    audit = await stored(audit_id)
    assert collector.await_count == 1
    assert audit.status is AuditStatus.failed
    assert "internal_field" not in audit.error_message


async def test_too_long_flood_wait_fails_instead_of_retrying(
    audit_id: UUID,
    stored: Callable,
    collector: AsyncMock,
    ai_answer: AsyncMock,
) -> None:
    collector.side_effect = TelegramCollectorError(
        "Telegram FloodWait: повторите через 86400 сек.",
        retryable=True,
        retry_after=86400,
    )

    await run_task(audit_id)

    audit = await stored(audit_id)
    assert collector.await_count == 1
    assert audit.status is AuditStatus.failed
    assert "86400" in audit.error_message


async def test_very_long_error_still_reaches_database(
    audit_id: UUID,
    stored: Callable,
    collector: AsyncMock,
    ai_answer: AsyncMock,
) -> None:
    collector.side_effect = TelegramCollectorError("x" * 5000)

    await run_task(audit_id)

    audit = await stored(audit_id)
    assert audit.status is AuditStatus.failed
    assert len(audit.error_message) == 1024


async def test_unknown_audit_id_does_not_create_records(session_factory: async_sessionmaker) -> None:
    unknown_id = uuid4()

    result = await run_task(unknown_id)

    assert result.failed()
    async with session_factory() as session:
        assert await session.get(AuditRequest, unknown_id) is None


class TestRetryCountdown:
    def test_grows_with_each_attempt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(tasks.random, "uniform", lambda _a, _b: 0)
        error = TelegramCollectorError("сеть", retryable=True)

        assert [retry_countdown(error, n) for n in range(3)] == [10, 20, 40]

    def test_waits_at_least_as_long_as_telegram_asks(self) -> None:
        error = TelegramCollectorError("flood", retryable=True, retry_after=300)

        assert retry_countdown(error, 0) >= 300

    def test_broken_infrastructure_uses_plain_backoff(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(tasks.random, "uniform", lambda _a, _b: 0)

        assert retry_countdown(ConnectionError("db"), 1) == 20
