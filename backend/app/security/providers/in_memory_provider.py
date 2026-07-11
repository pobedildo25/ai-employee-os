from datetime import datetime
from uuid import UUID

from app.security.interfaces.security import SecurityStore
from app.security.models import APIKey, AuditEvent
from app.security.policies.retention_policy import AuditRetentionPolicy


class InMemorySecurityProvider(SecurityStore):
    def __init__(self, retention: AuditRetentionPolicy | None = None) -> None:
        self._keys: dict[UUID, APIKey] = {}
        self._hash_index: dict[str, UUID] = {}
        self._audit: list[AuditEvent] = []
        self._retention = retention or AuditRetentionPolicy()

    async def save_api_key(self, api_key: APIKey) -> APIKey:
        self._keys[api_key.id] = api_key
        self._hash_index[api_key.key_hash] = api_key.id
        return api_key

    async def get_api_key(self, key_id: UUID) -> APIKey | None:
        return self._keys.get(key_id)

    async def get_api_key_by_hash(self, key_hash: str) -> APIKey | None:
        key_id = self._hash_index.get(key_hash)
        if key_id is None:
            return None
        return self._keys.get(key_id)

    async def list_api_keys(self, *, limit: int = 100) -> list[APIKey]:
        keys = sorted(self._keys.values(), key=lambda item: item.created_at, reverse=True)
        return keys[:limit]

    async def save_audit_event(self, event: AuditEvent) -> AuditEvent:
        self._audit.append(event)
        overflow = self._retention.overflow(len(self._audit))
        if overflow:
            self._audit = self._audit[overflow:]
        return event

    async def list_audit_events(self, *, limit: int = 100) -> list[AuditEvent]:
        return list(reversed(self._audit[-limit:]))


class APIKeyProvider:
    """Hash/generate helpers for API keys — never stores raw tokens."""

    @staticmethod
    def generate_raw_key() -> str:
        import secrets

        return f"aeo_{secrets.token_urlsafe(32)}"

    @staticmethod
    def hash_key(raw_key: str) -> str:
        import hashlib

        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    @staticmethod
    def touch(api_key: APIKey) -> APIKey:
        api_key.last_used_at = datetime.now()
        return api_key
