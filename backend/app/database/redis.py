import logging

import redis.asyncio as aioredis

from app.core.config import Settings

logger = logging.getLogger(__name__)

_client: aioredis.Redis | None = None


def get_redis_client(settings: Settings) -> aioredis.Redis:
    global _client
    if _client is None:
        _client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _client


async def check_redis(settings: Settings) -> tuple[bool, str]:
    try:
        client = get_redis_client(settings)
        await client.ping()
        return True, "ok"
    except Exception as exc:
        logger.warning("Redis health check failed: %s", exc)
        return False, str(exc)


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
