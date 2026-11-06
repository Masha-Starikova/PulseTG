from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.core.config import settings
from backend.telegram import session_manager
from backend.telegram.session_manager import TelegramSessionError, get_telegram_client


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Настройки Telegram заданы, session-файл лежит во временной папке."""
    monkeypatch.setattr(settings, "telegram_api_id", 12345)
    monkeypatch.setattr(settings, "telegram_api_hash", "test-hash")
    monkeypatch.setattr(settings, "telegram_session_name", "pulsetg_test")
    monkeypatch.setattr(session_manager, "SESSION_DIR", tmp_path)
    return tmp_path


async def test_missing_credentials_are_rejected() -> None:
    with pytest.raises(TelegramSessionError, match="TELEGRAM_API_ID"):
        await get_telegram_client()


@pytest.mark.parametrize("name", ["", "   ", ".session"])
async def test_invalid_session_name_is_rejected(
    configured: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
) -> None:
    monkeypatch.setattr(settings, "telegram_session_name", name)

    with pytest.raises(TelegramSessionError):
        await get_telegram_client()


async def test_missing_session_file_is_rejected(configured: Path) -> None:
    with pytest.raises(TelegramSessionError, match="Session-файл не найден"):
        await get_telegram_client()


async def test_session_name_cannot_escape_session_directory(
    configured: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "telegram_session_name", "../../etc/secret.session")

    with pytest.raises(TelegramSessionError) as exc_info:
        await get_telegram_client()

    assert str(configured / "secret.session") in str(exc_info.value)


def fake_telethon(monkeypatch: pytest.MonkeyPatch, authorized: bool) -> MagicMock:
    client = MagicMock()
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    client.is_user_authorized = AsyncMock(return_value=authorized)
    monkeypatch.setattr(session_manager, "TelegramClient", MagicMock(return_value=client))
    return client


async def test_returns_authorized_client(configured: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (configured / "pulsetg_test.session").touch()
    client = fake_telethon(monkeypatch, authorized=True)

    assert await get_telegram_client() is client
    client.connect.assert_awaited_once()


async def test_unauthorized_session_is_rejected_and_disconnected(
    configured: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (configured / "pulsetg_test.session").touch()
    client = fake_telethon(monkeypatch, authorized=False)

    with pytest.raises(TelegramSessionError, match="не авторизован"):
        await get_telegram_client()

    client.disconnect.assert_awaited_once()
