from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.models.audit import AuditStatus


class AuditCreateRequest(BaseModel):
    channel_username: str = Field(min_length=3, max_length=255)


class AuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    channel_username: str
    status: AuditStatus
    report: dict | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
