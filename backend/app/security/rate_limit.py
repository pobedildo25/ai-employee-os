from datetime import datetime, timedelta


class RateLimiter:
    """In-memory rate limiter — no Redis."""

    def __init__(self, *, limit: int = 60, window_seconds: int = 60) -> None:
        if limit < 1 or window_seconds < 1:
            raise ValueError("limit and window_seconds must be >= 1")
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, list[datetime]] = {}

    def allow(self, identifier: str) -> bool:
        now = datetime.now()
        window_start = now - timedelta(seconds=self.window_seconds)
        hits = [ts for ts in self._hits.get(identifier, []) if ts >= window_start]
        if len(hits) >= self.limit:
            self._hits[identifier] = hits
            return False
        hits.append(now)
        self._hits[identifier] = hits
        return True

    def remaining(self, identifier: str) -> int:
        now = datetime.now()
        window_start = now - timedelta(seconds=self.window_seconds)
        hits = [ts for ts in self._hits.get(identifier, []) if ts >= window_start]
        return max(0, self.limit - len(hits))
