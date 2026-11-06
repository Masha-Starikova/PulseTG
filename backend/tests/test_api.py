import sys
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

import backend.core.redis as redis_state
from backend.core.database import get_db_session
from backend.main import app
from backend.models import AuditRequest, AuditStatus
from backend.tests.conftest import TEST_REDIS_URL

pytestmark = pytest.mark.integration


@pytest.fixture
def queue(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Подмена Celery-задачи: брокер в API-тестах не участвует."""
    task = MagicMock()
    # backend.api экспортирует объект router, поэтому модуль берём из sys.modules.
    monkeypatch.setattr(sys.modules["backend.api.router"], "run_channel_audit", task)
    return task


class TestCreateAudit:
    async def test_creates_pending_audit_and_queues_task(
        self,
        client: httpx.AsyncClient,
        db_session: AsyncSession,
        queue: MagicMock,
    ) -> None:
        response = await client.post("/api/v1/audits", json={"channel_username": "@durov_news"})

        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "pending"
        assert body["channel_username"] == "durov_news"
        assert body["report"] is None

        stored = await db_session.get(AuditRequest, UUID(body["id"]))
        assert stored is not None
        queue.delay.assert_called_once_with(body["id"])

    @pytest.mark.parametrize(
        "payload",
        [{}, {"channel_username": 123}, {"channel_username": "ab"}, {"channel_username": "a" * 256}],
        ids=["missing", "wrong-type", "too-short", "too-long"],
    )
    async def test_invalid_body_is_rejected(
        self,
        client: httpx.AsyncClient,
        queue: MagicMock,
        payload: dict,
    ) -> None:
        response = await client.post("/api/v1/audits", json=payload)

        assert response.status_code == 422
        queue.delay.assert_not_called()


class TestGetAudit:
    async def test_returns_saved_audit(self, client: httpx.AsyncClient, db_session: AsyncSession) -> None:
        audit = AuditRequest(
            channel_username="channel",
            status=AuditStatus.completed,
            report={"channel": "channel", "metrics": {"summary": {"avg_er": 1.5}}},
        )
        db_session.add(audit)
        await db_session.commit()

        response = await client.get(f"/api/v1/audits/{audit.id}")

        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        assert response.json()["report"]["metrics"]["summary"]["avg_er"] == 1.5

    async def test_unknown_id_gives_404(self, client: httpx.AsyncClient) -> None:
        response = await client.get(f"/api/v1/audits/{uuid4()}")

        assert response.status_code == 404

    async def test_malformed_id_gives_422(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/api/v1/audits/not-a-uuid")

        assert response.status_code == 422


class TestHealth:
    @pytest.fixture
    async def real_redis(self, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Redis]:
        redis = Redis.from_url(TEST_REDIS_URL)
        monkeypatch.setattr(redis_state, "redis_client", redis)
        yield redis
        await redis.aclose()

    async def test_ok_with_real_postgres_and_redis(
        self,
        client: httpx.AsyncClient,
        real_redis: Redis,
    ) -> None:
        response = await client.get("/api/v1/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "db": "ok", "redis": "ok"}

    async def test_degraded_when_redis_does_not_respond(
        self,
        client: httpx.AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        broken_redis = MagicMock()
        broken_redis.ping = AsyncMock(side_effect=ConnectionError("redis down"))
        monkeypatch.setattr(redis_state, "redis_client", broken_redis)

        response = await client.get("/api/v1/health")

        assert response.json() == {"status": "degraded", "db": "ok", "redis": "error"}

    async def test_degraded_when_database_does_not_respond(self, client: httpx.AsyncClient) -> None:
        async def broken_session() -> AsyncIterator[MagicMock]:
            session = MagicMock()
            session.execute = AsyncMock(side_effect=ConnectionError("db down"))
            yield session

        app.dependency_overrides[get_db_session] = broken_session
        try:
            response = await client.get("/api/v1/health")
        finally:
            app.dependency_overrides.clear()

        assert response.json()["status"] == "degraded"
        assert response.json()["db"] == "error"


class TestRateLimit:
    async def test_sixth_create_within_minute_gets_429(
        self,
        client: httpx.AsyncClient,
        queue: MagicMock,
    ) -> None:
        for _ in range(5):
            response = await client.post("/api/v1/audits", json={"channel_username": "channel"})
            assert response.status_code == 202

        response = await client.post("/api/v1/audits", json={"channel_username": "channel"})

        assert response.status_code == 429
        assert queue.delay.call_count == 5

    async def test_thirty_first_read_within_minute_gets_429(self, client: httpx.AsyncClient) -> None:
        url = f"/api/v1/audits/{uuid4()}"
        for _ in range(30):
            assert (await client.get(url)).status_code == 404

        assert (await client.get(url)).status_code == 429

    async def test_limit_is_counted_per_client_address(
        self,
        client: httpx.AsyncClient,
        queue: MagicMock,
    ) -> None:
        for _ in range(5):
            await client.post("/api/v1/audits", json={"channel_username": "channel"})

        transport = httpx.ASGITransport(app=app, client=("10.0.0.2", 123))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as other_client:
            response = await other_client.post("/api/v1/audits", json={"channel_username": "channel"})

        assert response.status_code == 202


async def test_root_reports_service_is_running(client: httpx.AsyncClient) -> None:
    response = await client.get("/")

    assert response.status_code == 200
    assert response.json()["status"] == "running"
