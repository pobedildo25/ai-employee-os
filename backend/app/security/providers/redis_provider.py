"""Redis-backed security store for API keys and audit events (Sprint D starter)."""

from __future__ import annotations

import logging
from uuid import UUID

import redis.asyncio as aioredis

from app.security.interfaces.security import SecurityStore
from app.security.models import APIKey, AuditEvent
from app.security.policies.retention_policy import AuditRetentionPolicy

logger = logging.getLogger(__name__)

API_KEY_KEY = "security:apikey:{id}"
API_KEY_HASH_KEY = "security:apikey:hash:{hash}"
API_KEY_INDEX = "security:apikey:ids"
AUDIT_KEY = "security:audit"


class RedisSecurityProvider(SecurityStore):
    """Persist API keys + audit log in Redis JSON keys with a capped audit list."""

    def __init__(
        self,
        client: aioredis.Redis,
        retention: AuditRetentionPolicy | None = None,
    ) -> None:
        self._client = client
        self._retention = retention or AuditRetentionPolicy()

    async def save_api_key(self, api_key: APIKey) -> APIKey:
        payload = api_key.model_dump_json()
        pipe = self._client.pipeline()
        pipe.set(API_KEY_KEY.format(id=api_key.id), payload)
        pipe.set(API_KEY_HASH_KEY.format(hash=api_key.key_hash), str(api_key.id))
        score = api_key.created_at.timestamp()
        pipe.zadd(API_KEY_INDEX, {str(api_key.id): score})
        await pipe.execute()
        return api_key

    async def get_api_key(self, key_id: UUID) -> APIKey | None:
        raw = await self._client.get(API_KEY_KEY.format(id=key_id))
        if raw is None:
            return None
        return APIKey.model_validate_json(raw)

    async def get_api_key_by_hash(self, key_hash: str) -> APIKey | None:
        key_id_raw = await self._client.get(API_KEY_HASH_KEY.format(hash=key_hash))
        if key_id_raw is None:
            return None
        try:
            return await self.get_api_key(UUID(str(key_id_raw)))
        except ValueError:
            return None

    async def list_api_keys(self, *, limit: int = 100) -> list[APIKey]:
        ids = await self._client.zrevrange(API_KEY_INDEX, 0, max(0, limit - 1))
        keys: list[APIKey] = []
        for key_id_raw in ids or []:
            try:
                record = await self.get_api_key(UUID(str(key_id_raw)))
            except ValueError:
                continue
            if record is not None:
                keys.append(record)
        return keys

    async def save_audit_event(self, event: AuditEvent) -> AuditEvent:
        await self._client.rpush(AUDIT_KEY, event.model_dump_json())
        overflow = self._retention.overflow(await self._client.llen(AUDIT_KEY))
        if overflow:
            await self._client.ltrim(AUDIT_KEY, overflow, -1)
        return event

    async def list_audit_events(self, *, limit: int = 100) -> list[AuditEvent]:
        raw_items = await self._client.lrange(AUDIT_KEY, -max(1, limit), -1)
        events = [AuditEvent.model_validate_json(raw) for raw in raw_items or []]
        events.reverse()
        return events
