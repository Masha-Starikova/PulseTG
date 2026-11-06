import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.models.audit import AuditStatus

# Правила Telegram: 5-32 символа, латиница, цифры и _, начало с буквы,
# без двойного подчёркивания и без _ в конце.
TELEGRAM_USERNAME_PATTERN = re.compile(r"[A-Za-z](?!\w*__)\w{3,30}[A-Za-z0-9]", re.ASCII)
TELEGRAM_LINK_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?(?:t|telegram)\.me/(?P<name>[^/?#]+)/?(?:\?.*)?",
    re.IGNORECASE,
)


class AuditCreateRequest(BaseModel):
    channel_username: str = Field(min_length=3, max_length=255)

    @field_validator("channel_username")
    @classmethod
    def normalize_channel_username(cls, value: str) -> str:
        """Принимает name, @name и ссылку t.me/name, возвращает голое имя канала."""
        raw = value.strip()
        link = TELEGRAM_LINK_PATTERN.fullmatch(raw)
        name = link.group("name") if link else raw.removeprefix("@")

        if not TELEGRAM_USERNAME_PATTERN.fullmatch(name):
            raise ValueError("Укажите публичный Telegram-канал в формате @name или t.me/name")
        return name


class AuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    channel_username: str
    status: AuditStatus
    report: dict | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
