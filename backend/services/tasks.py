import asyncio
import logging
import random

from sqlalchemy.exc import InterfaceError, OperationalError

from backend.core.celery_app import celery_app
from backend.core.database import AsyncSessionLocal
from backend.core.errors import AuditError
from backend.services.audit_service import AuditService

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BASE_RETRY_DELAY_SECONDS = 10
RETRY_JITTER_SECONDS = 5
# Отложенная задача в Redis-брокере не должна пережить visibility timeout (1 час),
# поэтому слишком долгий FloodWait считаем провалом, а не ждём его.
MAX_RETRY_DELAY_SECONDS = 15 * 60
UNEXPECTED_ERROR_MESSAGE = "Внутренняя ошибка при выполнении аудита"

# Сбои инфраструктуры (база, сеть воркера) тоже временные.
TRANSIENT_INFRASTRUCTURE_ERRORS = (OSError, OperationalError, InterfaceError)


def retry_countdown(exc: Exception, retries_done: int) -> float:
    """Экспоненциальная пауза с разбросом, но не меньше, чем просит внешний сервис."""
    backoff = BASE_RETRY_DELAY_SECONDS * 2**retries_done
    jitter = random.uniform(0, RETRY_JITTER_SECONDS)
    return max(backoff + jitter, getattr(exc, "retry_after", None) or 0)


def _should_retry(exc: Exception) -> bool:
    if isinstance(exc, AuditError):
        retry_after = exc.retry_after or 0
        return exc.retryable and retry_after <= MAX_RETRY_DELAY_SECONDS
    return isinstance(exc, TRANSIENT_INFRASTRUCTURE_ERRORS)


def _failure_message(exc: Exception) -> str:
    return str(exc) if isinstance(exc, AuditError) else UNEXPECTED_ERROR_MESSAGE


@celery_app.task(bind=True, name="audit.run_channel_audit", max_retries=MAX_RETRIES)
def run_channel_audit(self, audit_id: str) -> dict:
    """Запуск полного цикла аудита в Celery-воркере.

    Временные ошибки повторяются, постоянные сразу завершают аудит.
    Статус failed ставится только когда повторов больше не будет.
    """

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # В некоторых окружениях Celery event loop может быть не инициализирован.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        return loop.run_until_complete(_run_channel_audit(audit_id))
    except Exception as exc:
        if _should_retry(exc) and self.request.retries < self.max_retries:
            countdown = retry_countdown(exc, self.request.retries)
            logger.warning("Audit %s: повтор через %.0f сек: %s", audit_id, countdown, exc)
            raise self.retry(exc=exc, countdown=countdown)

        logger.exception("Audit %s завершился ошибкой", audit_id)
        loop.run_until_complete(_mark_failed(audit_id, _failure_message(exc)))
        raise


async def _run_channel_audit(audit_id: str) -> dict:
    async with AsyncSessionLocal() as session:
        service = AuditService(session=session)
        audit = await service.run_audit(audit_id)
        logger.info("Audit %s completed with status=%s", audit.id, audit.status.value)
        return {
            "audit_id": str(audit.id),
            "status": audit.status.value,
        }


async def _mark_failed(audit_id: str, message: str) -> None:
    async with AsyncSessionLocal() as session:
        await AuditService(session=session).mark_failed(audit_id, message)
