from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.ai.client import AIClientError
from backend.ai.service import AIInsightsService
from backend.models import AuditRequest, AuditStatus
from backend.services.audit_service import AuditService
from backend.tests.factories import VALID_REPORT_TEXT

pytestmark = pytest.mark.integration


class TestCreateAndRead:
    @pytest.mark.parametrize("raw", ["channel", "@channel", "  @channel  "])
    async def test_channel_is_normalized_and_stored(self, db_session: AsyncSession, raw: str) -> None:
        audit = await AuditService(db_session).create_audit_request(raw)

        stored = await db_session.get(AuditRequest, audit.id)
        assert stored.channel_username == "channel"
        assert stored.status is AuditStatus.pending
        assert stored.created_at is not None

    async def test_get_returns_none_for_unknown_or_malformed_id(self, db_session: AsyncSession) -> None:
        service = AuditService(db_session)

        assert await service.get_audit_request(str(uuid4())) is None
        assert await service.get_audit_request("not-a-uuid") is None


POSTS = [
    {
        "id": 1,
        "date": "2026-03-02T10:00:00+00:00",
        "text": "пост",
        "views": 100,
        "reactions": 5,
        "forwards": 1,
        "comments_count": 0,
    }
]


def make_service(session: AsyncSession, *ai_answers: str | Exception) -> AuditService:
    service = AuditService(session)
    ai_client = MagicMock()
    ai_client.generate_insight = AsyncMock(side_effect=list(ai_answers))
    service.ai_service = AIInsightsService(client=ai_client)
    return service


@pytest.fixture
def collector(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock = AsyncMock(return_value=POSTS)
    monkeypatch.setattr("backend.services.audit_service.get_channel_posts", mock)
    return mock


async def stored_audit(factory: async_sessionmaker[AsyncSession], audit_id: UUID) -> AuditRequest:
    """Читает запись отдельной сессией: видно только то, что реально закоммичено."""
    async with factory() as session:
        return await session.get(AuditRequest, audit_id)


class TestRunAudit:
    async def test_success_goes_through_running_to_completed(
        self,
        db_session: AsyncSession,
        session_factory: async_sessionmaker[AsyncSession],
        collector: AsyncMock,
    ) -> None:
        service = make_service(db_session, VALID_REPORT_TEXT)
        audit = await service.create_audit_request("channel")
        seen_statuses: list[AuditStatus] = []

        async def collect(*_args: object, **_kwargs: object) -> list[dict]:
            seen_statuses.append((await stored_audit(session_factory, audit.id)).status)
            return POSTS

        collector.side_effect = collect

        await service.run_audit(str(audit.id))

        assert seen_statuses == [AuditStatus.running]
        stored = await stored_audit(session_factory, audit.id)
        assert stored.status is AuditStatus.completed
        assert stored.error_message is None
        assert stored.report["channel"] == "channel"
        assert stored.report["metrics"]["summary"]["posts_count"] == 1
        assert stored.report["ai"]["status"] == "ok"
        assert stored.report["posts"] == POSTS

    async def test_failure_propagates_and_keeps_audit_for_retry(
        self,
        db_session: AsyncSession,
        session_factory: async_sessionmaker[AsyncSession],
        collector: AsyncMock,
    ) -> None:
        service = make_service(db_session, AIClientError("Превышен лимит OpenAI API"))
        audit = await service.create_audit_request("channel")

        with pytest.raises(AIClientError, match="лимит"):
            await service.run_audit(str(audit.id))

        stored = await stored_audit(session_factory, audit.id)
        assert stored.status is AuditStatus.running
        assert stored.report is None

    async def test_missing_ai_key_is_reported(
        self,
        db_session: AsyncSession,
        collector: AsyncMock,
    ) -> None:
        service = AuditService(db_session)
        audit = await service.create_audit_request("channel")

        with pytest.raises(AIClientError, match="OPENAI_API_KEY"):
            await service.run_audit(str(audit.id))

    async def test_unknown_audit_is_an_error(self, db_session: AsyncSession) -> None:
        with pytest.raises(ValueError, match="not found"):
            await AuditService(db_session).run_audit(str(uuid4()))


class TestMarkFailed:
    async def test_saves_reason(
        self,
        db_session: AsyncSession,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        service = AuditService(db_session)
        audit = await service.create_audit_request("channel")

        await service.mark_failed(str(audit.id), "Канал не найден")

        stored = await stored_audit(session_factory, audit.id)
        assert stored.status is AuditStatus.failed
        assert stored.error_message == "Канал не найден"

    async def test_unknown_audit_is_ignored(self, db_session: AsyncSession) -> None:
        await AuditService(db_session).mark_failed(str(uuid4()), "ошибка")
