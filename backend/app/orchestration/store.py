"""ExecutionStore — durable orchestration lifecycle for API / multi-worker.

In-memory implementation remains for unit tests. Production wiring uses Redis.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from threading import Lock
from typing import Protocol

from app.core.config import Settings, get_settings
from app.orchestration.models import ExecutionRecord, ExecutionState

logger = logging.getLogger(__name__)

EXECUTION_KEY = "orchestration:execution:{execution_id}"
EXECUTION_INDEX_KEY = "orchestration:execution:ids"
DEFAULT_TTL_SECONDS = 604800


class ExecutionStore(Protocol):
    def save(self, record: ExecutionRecord) -> None: ...

    def get(self, execution_id: str) -> ExecutionRecord | None: ...

    def update_state(self, execution_id: str, state: ExecutionState) -> ExecutionRecord | None: ...

    def list_ids(self) -> list[str]: ...


class InMemoryExecutionStore:
    """Process-local store for tests / single-process tooling."""

    def __init__(self) -> None:
        self._records: dict[str, ExecutionRecord] = {}
        self._lock = Lock()

    def save(self, record: ExecutionRecord) -> None:
        with self._lock:
            self._records[record.execution_id] = record

    def get(self, execution_id: str) -> ExecutionRecord | None:
        with self._lock:
            return self._records.get(execution_id)

    def update_state(self, execution_id: str, state: ExecutionState) -> ExecutionRecord | None:
        with self._lock:
            record = self._records.get(execution_id)
            if record is None:
                return None
            record.state = state
            self._records[execution_id] = record
            return record

    def list_ids(self) -> list[str]:
        with self._lock:
            return list(self._records.keys())


# Backward-compatible alias used widely in tests.
ExecutionStoreImpl = InMemoryExecutionStore


class RedisExecutionStore:
    """Shared Redis-backed ExecutionStore — restart / multi-worker safe."""

    def __init__(
        self,
        redis_url: str,
        *,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        client=None,
    ) -> None:
        if client is None:
            import redis

            client = redis.from_url(redis_url, encoding="utf-8", decode_responses=True)
        self._client = client
        self._ttl = ttl_seconds

    def _key(self, execution_id: str) -> str:
        return EXECUTION_KEY.format(execution_id=execution_id)

    def save(self, record: ExecutionRecord) -> None:
        payload = record.model_dump_json()
        pipe = self._client.pipeline()
        pipe.set(self._key(record.execution_id), payload, ex=self._ttl)
        pipe.sadd(EXECUTION_INDEX_KEY, record.execution_id)
        pipe.expire(EXECUTION_INDEX_KEY, self._ttl)
        pipe.execute()

    def get(self, execution_id: str) -> ExecutionRecord | None:
        raw = self._client.get(self._key(execution_id))
        if raw is None:
            return None
        return ExecutionRecord.model_validate_json(raw)

    def update_state(self, execution_id: str, state: ExecutionState) -> ExecutionRecord | None:
        record = self.get(execution_id)
        if record is None:
            return None
        record.state = state
        self.save(record)
        return record

    def list_ids(self) -> list[str]:
        values = self._client.smembers(EXECUTION_INDEX_KEY) or set()
        return sorted(str(v) for v in values)


def create_execution_store(settings: Settings | None = None) -> InMemoryExecutionStore | RedisExecutionStore:
    """Prefer Redis whenever a redis_url is configured; otherwise in-memory."""
    cfg = settings or get_settings()
    redis_url = (cfg.redis_url or "").strip()
    if redis_url:
        try:
            store = RedisExecutionStore(redis_url, ttl_seconds=cfg.checkpoint_ttl_seconds or DEFAULT_TTL_SECONDS)
            # Touch Redis early so misconfig fails at wiring time.
            store.list_ids()
            logger.info("using RedisExecutionStore | redis_url=%s", redis_url)
            return store
        except Exception as exc:
            if cfg.is_production:
                raise RuntimeError(
                    "RedisExecutionStore required but Redis is unavailable"
                ) from exc
            logger.warning(
                "RedisExecutionStore unavailable, falling back to in-memory | error=%s",
                exc,
            )
    return InMemoryExecutionStore()


@lru_cache
def get_execution_store_singleton() -> InMemoryExecutionStore | RedisExecutionStore:
    return create_execution_store()


# Historical name used by older imports/tests.
ExecutionStore = InMemoryExecutionStore  # type: ignore[misc, assignment]
