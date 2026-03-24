from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import backend.core.redis as redis_state
from backend.core.database import get_db_session
from backend.core.rate_limit import limiter
from backend.schemas import AuditCreateRequest, AuditResponse, HealthResponse
from backend.services.audit_service import AuditService
from backend.services.tasks import run_channel_audit

router = APIRouter(prefix="/api/v1", tags=["v1"])


@router.get("/health", response_model=HealthResponse)
async def healthcheck(session: AsyncSession = Depends(get_db_session)) -> HealthResponse:
    db_status = "ok"
    redis_status = "ok"

    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    try:
        if redis_state.redis_client is None:
            redis_status = "disconnected"
        else:
            await redis_state.redis_client.ping()
    except Exception:
        redis_status = "error"

    status_value = "ok" if db_status == "ok" and redis_status in {"ok", "disconnected"} else "degraded"
    return HealthResponse(status=status_value, db=db_status, redis=redis_status)


@router.post("/audits", response_model=AuditResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
async def create_audit(
    request: Request,
    payload: AuditCreateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> AuditResponse:
    service = AuditService(session=session)
    audit = await service.create_audit_request(payload.channel_username)

    # Запускаем асинхронную задачу обработки в Celery-воркере.
    run_channel_audit.delay(str(audit.id))
    return AuditResponse.model_validate(audit)


@router.get("/audits/{audit_id}", response_model=AuditResponse)
@limiter.limit("30/minute")
async def get_audit(
    request: Request,
    audit_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> AuditResponse:
    service = AuditService(session=session)
    audit = await service.get_audit_request(str(audit_id))
    if audit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit not found")

    return AuditResponse.model_validate(audit)
