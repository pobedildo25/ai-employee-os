from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Protocol


class RateLimiterProtocol(Protocol):
    async def allow(self, identifier: str) -> bool: ...

    async def remaining(self, identifier: str) -> int: ...


class RateLimiter:
    """In-memory fixed-window rate limiter (tests / single process)."""

    def __init__(self, *, limit: int = 60, window_seconds: int = 60) -> None:
        if limit < 1 or window_seconds < 1:
            raise ValueError("limit and window_seconds must be >= 1")
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, list[datetime]] = {}

    async def allow(self, identifier: str) -> bool:
        now = datetime.now()
        window_start = now - timedelta(seconds=self.window_seconds)
        hits = [ts for ts in self._hits.get(identifier, []) if ts >= window_start]
        if len(hits) >= self.limit:
            self._hits[identifier] = hits
            return False
        hits.append(now)
        self._hits[identifier] = hits
        return True

    async def remaining(self, identifier: str) -> int:
        now = datetime.now()
        window_start = now - timedelta(seconds=self.window_seconds)
        hits = [ts for ts in self._hits.get(identifier, []) if ts >= window_start]
        return max(0, self.limit - len(hits))


class RedisRateLimiter:
    """Shared fixed-window rate limiter backed by Redis INCR + EXPIRE."""

    def __init__(
        self,
        redis: Any,
        *,
        limit: int = 60,
        window_seconds: int = 60,
        key_prefix: str = "ratelimit:",
    ) -> None:
        if limit < 1 or window_seconds < 1:
            raise ValueError("limit and window_seconds must be >= 1")
        self._redis = redis
        self.limit = limit
        self.window_seconds = window_seconds
        self._key_prefix = key_prefix
        self._fallback = RateLimiter(limit=limit, window_seconds=window_seconds)

    def _window_key(self, identifier: str) -> str:
        window_id = int(datetime.now().timestamp()) // self.window_seconds
        return f"{self._key_prefix}{identifier}:{window_id}"

    async def allow(self, identifier: str) -> bool:
        key = self._window_key(identifier)
        try:
            count = await self._redis.incr(key)
            if count == 1:
                await self._redis.expire(key, self.window_seconds)
            return int(count) <= self.limit
        except Exception:
            return await self._fallback.allow(identifier)

    async def remaining(self, identifier: str) -> int:
        key = self._window_key(identifier)
        try:
            raw = await self._redis.get(key)
            count = int(raw) if raw is not None else 0
            return max(0, self.limit - count)
        except Exception:
            return await self._fallback.remaining(identifier)


def create_rate_limiter(
    *,
    limit: int,
    window_seconds: int,
    redis: Any | None = None,
) -> RateLimiter | RedisRateLimiter:
    if redis is not None:
        return RedisRateLimiter(redis, limit=limit, window_seconds=window_seconds)
    return RateLimiter(limit=limit, window_seconds=window_seconds)
