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

    async def test_ai_failure_is_not_shown_as_success(
        self,
        db_session: AsyncSession,
        session_factory: async_sessionmaker[AsyncSession],
        collector: AsyncMock,
    ) -> None:
        service = make_service(db_session, AIClientError("Превышен лимит OpenAI API"))
        audit = await service.create_audit_request("channel")

        await service.run_audit(str(audit.id))

        stored = await stored_audit(session_factory, audit.id)
        assert stored.status is AuditStatus.failed
        assert "лимит" in stored.error_message
        assert stored.report is None

    async def test_missing_ai_key_fails_audit_with_clear_reason(
        self,
        db_session: AsyncSession,
        session_factory: async_sessionmaker[AsyncSession],
        collector: AsyncMock,
    ) -> None:
        service = AuditService(db_session)
        audit = await service.create_audit_request("channel")

        await service.run_audit(str(audit.id))

        stored = await stored_audit(session_factory, audit.id)
        assert stored.status is AuditStatus.failed
        assert "OPENAI_API_KEY" in stored.error_message
