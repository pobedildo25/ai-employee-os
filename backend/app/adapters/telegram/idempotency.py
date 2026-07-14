"""Idempotent Telegram update claiming via Redis SET NX (fail-closed)."""

from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)

UPDATE_KEY_PREFIX = "telegram:update:"
DEFAULT_TTL_SECONDS = 86_400


class RedisSetClient(Protocol):
    async def set(
        self,
        key: str,
        value: str,
        ex: int | None = None,
        nx: bool = False,
    ) -> Any: ...


async def claim_telegram_update(
    redis: RedisSetClient | None,
    update_id: int | str,
    *,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> bool:
    """Return True if this process should handle the update; False if duplicate.

    When redis is None, claims (single-process/tests without shared Redis).
    When Redis errors, fail-closed (do not process) — better drop than double-execute.
    """
    if redis is None:
        return True
    key = f"{UPDATE_KEY_PREFIX}{update_id}"
    try:
        result = await redis.set(key, "1", ex=ttl_seconds, nx=True)
    except Exception as exc:  # noqa: BLE001 — fail closed
        logger.error(
            "telegram idempotency claim failed; dropping update | update_id=%s error=%s",
            update_id,
            exc,
        )
        return False
    # redis-py: True when set, None/False when NX fails
    return bool(result)
