from redis.asyncio import Redis

from backend.core.config import settings

redis_client: Redis | None = None


async def init_redis() -> Redis:
    """Инициализация общего Redis-клиента."""

    global redis_client
    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    await redis_client.ping()
    return redis_client


async def close_redis() -> None:
    """Корректное завершение соединения с Redis."""

    global redis_client
    if redis_client is not None:
        await redis_client.close()
        redis_client = None
