from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TypedDict

from telethon.errors import (
    ChannelPrivateError,
    FloodWaitError,
    RPCError,
    UsernameInvalidError,
    UsernameNotOccupiedError,
)

from backend.telegram.session_manager import TelegramSessionError, get_telegram_client

logger = logging.getLogger(__name__)


class ChannelPost(TypedDict):
    id: int
    date: str
    text: str
    views: int
    reactions: int
    forwards: int
    comments_count: int


class TelegramCollectorError(RuntimeError):
    """Базовая ошибка модуля Telegram collector."""


async def get_channel_posts(channel_username: str, days: int = 30) -> list[ChannelPost]:
    """Возвращает список постов канала за последние `days` дней."""

    # Проверяем базовые входные параметры до сетевого вызова.
    normalized_username = channel_username.strip().lstrip("@")
    if not normalized_username:
        raise TelegramCollectorError("channel_username не должен быть пустым")
    if days <= 0:
        raise TelegramCollectorError("days должен быть положительным числом")

    cutoff_dt = datetime.now(tz=UTC) - timedelta(days=days)
    posts: list[ChannelPost] = []

    try:
        client = await get_telegram_client()
        try:
            entity = await client.get_entity(normalized_username)

            # iter_messages возвращает сообщения от новых к старым,
            # поэтому завершаем обход, когда дошли до даты отсечения.
            async for message in client.iter_messages(entity):
                if message.date is None:
                    continue
                if message.date < cutoff_dt:
                    break

                reactions_count = 0
                if message.reactions and message.reactions.results:
                    reactions_count = sum(item.count for item in message.reactions.results)

                comments_count = 0
                if message.replies and message.replies.replies:
                    comments_count = int(message.replies.replies)

                posts.append(
                    {
                        "id": int(message.id),
                        "date": message.date.isoformat(),
                        "text": message.message or "",
                        "views": int(message.views or 0),
                        "reactions": int(reactions_count),
                        "forwards": int(message.forwards or 0),
                        "comments_count": comments_count,
                    }
                )
        finally:
            if client.is_connected():
                await client.disconnect()
    except TelegramSessionError as exc:
        raise TelegramCollectorError(str(exc)) from exc
    except (UsernameInvalidError, UsernameNotOccupiedError) as exc:
        raise TelegramCollectorError("Канал не найден или указан некорректный username") from exc
    except ChannelPrivateError as exc:
        raise TelegramCollectorError("Канал приватный или недоступен текущей сессии") from exc
    except FloodWaitError as exc:
        raise TelegramCollectorError(f"Telegram FloodWait: повторите попытку через {exc.seconds} сек.") from exc
    except RPCError as exc:
        raise TelegramCollectorError(f"Ошибка Telegram API: {exc.__class__.__name__}") from exc
    except Exception as exc:
        logger.exception("Непредвиденная ошибка при сборе постов канала: %s", normalized_username)
        raise TelegramCollectorError("Не удалось получить посты канала") from exc

    return posts
