from backend.telegram.telegram_collector import get_channel_posts


class TelegramCollector:
    """Совместимый wrapper для старого интерфейса TelegramCollector."""

    async def fetch_channel_data(self, channel_username: str, days: int = 30) -> dict:
        posts = await get_channel_posts(channel_username=channel_username, days=days)
        return {
            "channel": channel_username,
            "period_days": days,
            "posts": posts,
        }
