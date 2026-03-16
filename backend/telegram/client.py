from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from telethon import TelegramClient

from backend.core.config import settings


@dataclass(slots=True)
class TelegramCollector:
    """Сервис сбора данных из Telegram-канала."""

    api_id: int = settings.telegram_api_id
    api_hash: str = settings.telegram_api_hash
    session_name: str = settings.telegram_session_name

    async def fetch_channel_data(self, channel_username: str, days: int = 30) -> dict:
        if not self.api_id or not self.api_hash:
            raise RuntimeError("TELEGRAM_API_ID и TELEGRAM_API_HASH должны быть заданы")

        cutoff_dt = datetime.now(tz=UTC) - timedelta(days=days)

        posts: list[dict] = []
        async with TelegramClient(self.session_name, self.api_id, self.api_hash) as client:
            entity = await client.get_entity(channel_username)

            async for message in client.iter_messages(entity, limit=500):
                if message.date is None:
                    continue
                if message.date < cutoff_dt:
                    break

                reactions_count = 0
                if message.reactions and message.reactions.results:
                    reactions_count = sum(item.count for item in message.reactions.results)

                posts.append(
                    {
                        "id": message.id,
                        "date": message.date.isoformat(),
                        "views": message.views or 0,
                        "forwards": message.forwards or 0,
                        "replies": message.replies.replies if message.replies else 0,
                        "reactions": reactions_count,
                        "text_length": len(message.message or ""),
                    }
                )

        return {
            "channel": channel_username,
            "period_days": days,
            "posts": posts,
        }
