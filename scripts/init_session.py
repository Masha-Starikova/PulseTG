"""Временный скрипт для генерации Telethon session-файла.

Запускается локально один раз, чтобы создать авторизованный session,
который затем используется сервисами в runtime без интерактивного логина.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

from backend.core.config import Settings


async def main() -> None:
    # Подгружаем .env перед чтением настроек.
    load_dotenv()
    settings = Settings()
    
    print("API_ID:", settings.telegram_api_id)
    print("API_HASH:", settings.telegram_api_hash)

    if settings.telegram_api_id <= 0 or not settings.telegram_api_hash:
        raise RuntimeError("TELEGRAM_API_ID и TELEGRAM_API_HASH должны быть заданы в .env")

    session_dir = Path("backend/telegram")
    session_dir.mkdir(parents=True, exist_ok=True)

    session_name = (settings.telegram_session_name or "").strip()
    if not session_name:
        raise RuntimeError("TELEGRAM_SESSION_NAME не задан в .env")
    if session_name.endswith(".session"):
        session_name = session_name[: -len(".session")]

    session_base_path = session_dir / Path(session_name).name
    session_file_path = session_base_path.with_suffix(".session")

    async with TelegramClient(
        str(session_base_path),
        settings.telegram_api_id,
        settings.telegram_api_hash,
    ) as client:
        if not await client.is_user_authorized():
            # Это единственный шаг, где используется интерактивная авторизация.
            print("Авторизация Telegram session. Введите номер телефона и код подтверждения.")
            phone = input("Телефон (+7999...): ").strip()
            await client.send_code_request(phone)
            code = input("Код из Telegram: ").strip()

            try:
                await client.sign_in(phone=phone, code=code)
            except SessionPasswordNeededError:
                password = input("Пароль 2FA: ").strip()
                await client.sign_in(password=password)

    print(f"Session-файл успешно создан: {session_file_path}")


if __name__ == "__main__":
    asyncio.run(main())
