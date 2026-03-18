from pathlib import Path

from telethon import TelegramClient

from backend.core.config import settings

SESSION_DIR = Path("backend/telegram")


class TelegramSessionError(RuntimeError):
    """Ошибки управления Telegram-сессией."""


def _resolve_session_base_path() -> Path:
    """Возвращает путь до session без расширения .session."""

    session_name = (settings.telegram_session_name or "").strip()
    if not session_name:
        raise TelegramSessionError("TELEGRAM_SESSION_NAME не задан в .env")

    # Защищаемся от передачи вложенных путей через env.
    safe_name = Path(session_name).name
    if safe_name.endswith(".session"):
        safe_name = safe_name[: -len(".session")]

    if not safe_name:
        raise TelegramSessionError("Некорректное значение TELEGRAM_SESSION_NAME")

    return SESSION_DIR / safe_name


async def get_telegram_client() -> TelegramClient:
    """Возвращает готовый к работе авторизованный TelegramClient.

    В runtime не выполняем интерактивную авторизацию.
    Используется только существующий session-файл.
    """

    if settings.telegram_api_id <= 0 or not settings.telegram_api_hash:
        raise TelegramSessionError("TELEGRAM_API_ID и TELEGRAM_API_HASH должны быть заданы в .env")

    session_base_path = _resolve_session_base_path()
    session_file_path = session_base_path.with_suffix(".session")

    if not session_file_path.exists():
        raise TelegramSessionError(
            f"Session-файл не найден: {session_file_path}. "
            "Создайте его заранее через init_session.py"
        )

    client = TelegramClient(
        str(session_base_path),
        settings.telegram_api_id,
        settings.telegram_api_hash,
    )

    await client.connect()
    if not await client.is_user_authorized():
        await client.disconnect()
        raise TelegramSessionError(
            "Текущий session-файл не авторизован. "
            "Пересоздайте session через init_session.py"
        )

    return client
