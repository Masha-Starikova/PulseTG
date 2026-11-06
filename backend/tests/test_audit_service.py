from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import AuditRequest, AuditStatus
from backend.services.audit_service import AuditService

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
