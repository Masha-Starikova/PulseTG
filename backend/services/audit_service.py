from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.ai.service import AIInsightsService
from backend.analytics.analytics_engine import calculate_metrics
from backend.models.audit import AuditRequest, AuditStatus
from backend.telegram.telegram_collector import get_channel_posts


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.ai_service = AIInsightsService()

    async def create_audit_request(self, channel_username: str) -> AuditRequest:
        normalized_channel = channel_username.strip().lstrip("@")

        audit = AuditRequest(
            channel_username=normalized_channel,
            status=AuditStatus.pending,
        )
        self.session.add(audit)
        await self.session.commit()
        await self.session.refresh(audit)
        return audit

    async def get_audit_request(self, audit_id: str) -> AuditRequest | None:
        try:
            audit_uuid = UUID(audit_id)
        except ValueError:
            return None

        stmt = select(AuditRequest).where(AuditRequest.id == audit_uuid)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def run_audit(self, audit_id: str) -> AuditRequest:
        audit = await self.get_audit_request(audit_id)
        if audit is None:
            raise ValueError("Audit request not found")

        try:
            audit.status = AuditStatus.running
            await self.session.commit()

            period_days = 30
            posts = await get_channel_posts(audit.channel_username, days=period_days)
            metrics = calculate_metrics(posts)
            ai_report = await self.ai_service.generate_audit(
                metrics,
                channel_username=audit.channel_username,
                period_days=period_days,
            )

            audit.status = AuditStatus.completed
            audit.report = {
                "channel": audit.channel_username,
                "period_days": period_days,
                "posts": posts,
                "metrics": metrics,
                "ai": ai_report,
            }
            audit.error_message = None
            await self.session.commit()
            await self.session.refresh(audit)
            return audit
        except Exception as exc:
            audit.status = AuditStatus.failed
            audit.error_message = str(exc)
            await self.session.commit()
            await self.session.refresh(audit)
            return audit
