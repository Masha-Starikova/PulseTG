import asyncio
import logging

from backend.core.celery_app import celery_app
from backend.core.database import AsyncSessionLocal
from backend.services.audit_service import AuditService

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="audit.run_channel_audit",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def run_channel_audit(self, audit_id: str) -> dict:
    """Запуск полного цикла аудита в Celery-воркере."""

    return asyncio.run(_run_channel_audit(audit_id))


async def _run_channel_audit(audit_id: str) -> dict:
    async with AsyncSessionLocal() as session:
        service = AuditService(session=session)
        audit = await service.run_audit(audit_id)
        logger.info("Audit %s completed with status=%s", audit.id, audit.status.value)
        return {
            "audit_id": str(audit.id),
            "status": audit.status.value,
        }
