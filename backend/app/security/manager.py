from uuid import UUID

from app.security.interfaces.security import SecurityStore
from app.security.models import (
    APIKey,
    APIKeyCreateResult,
    APIKeyInfo,
    APIKeyStatus,
    AuditEvent,
    Role,
    SecurityPrincipal,
)
from app.security.permissions import permissions_for_role
from app.security.policies.access_policy import AccessPolicy
from app.security.providers.api_key_provider import APIKeyProvider
from app.security.providers.in_memory_provider import InMemorySecurityProvider
from app.security.rate_limit import RateLimiter
from app.security.secrets import SecretsManager


class SecurityManager:
    """Infrastructure security facade — no business decisions."""

    def __init__(
        self,
        store: SecurityStore | None = None,
        *,
        rate_limiter: RateLimiter | None = None,
        secrets: SecretsManager | None = None,
        access_policy: AccessPolicy | None = None,
    ) -> None:
        self._store = store or InMemorySecurityProvider()
        self.rate_limiter = rate_limiter or RateLimiter()
        self.secrets = secrets or SecretsManager()
        self.access_policy = access_policy or AccessPolicy()
        self._keys = APIKeyProvider()

    async def create_api_key(
        self,
        *,
        name: str,
        role: Role = Role.USER,
        permissions: list[str] | None = None,
        metadata: dict | None = None,
    ) -> APIKeyCreateResult:
        raw = self._keys.generate_raw_key()
        key_hash = self._keys.hash_key(raw)
        effective_permissions = permissions or permissions_for_role(role)
        record = APIKey(
            name=name,
            key_hash=key_hash,
            status=APIKeyStatus.ACTIVE,
            role=role,
            permissions=effective_permissions,
            metadata=metadata or {},
        )
        saved = await self._store.save_api_key(record)
        return APIKeyCreateResult(
            id=saved.id,
            name=saved.name,
            api_key=raw,
            status=saved.status,
            role=saved.role,
            permissions=saved.permissions,
            created_at=saved.created_at,
            metadata=saved.metadata,
        )

    async def validate_api_key(self, raw_key: str) -> SecurityPrincipal | None:
        key_hash = self._keys.hash_key(raw_key)
        record = await self._store.get_api_key_by_hash(key_hash)
        if record is None or record.status != APIKeyStatus.ACTIVE:
            return None
        touched = self._keys.touch(record)
        await self._store.save_api_key(touched)
        return SecurityPrincipal(
            actor=f"api_key:{record.id}",
            api_key_id=record.id,
            role=record.role,
            permissions=record.permissions,
        )

    async def revoke_api_key(self, key_id: UUID) -> APIKeyInfo | None:
        record = await self._store.get_api_key(key_id)
        if record is None:
            return None
        record.status = APIKeyStatus.REVOKED
        saved = await self._store.save_api_key(record)
        return self._to_info(saved)

    async def get_key_info(self, key_id: UUID) -> APIKeyInfo | None:
        record = await self._store.get_api_key(key_id)
        return self._to_info(record) if record else None

    async def list_keys(self, *, limit: int = 100) -> list[APIKeyInfo]:
        records = await self._store.list_api_keys(limit=limit)
        return [self._to_info(record) for record in records]

    def check_permission(self, principal: SecurityPrincipal, required: str) -> bool:
        return self.access_policy.allow(
            role=principal.role,
            granted=principal.permissions,
            required=required,
        )

    async def record_audit(
        self,
        *,
        actor: str,
        action: str,
        resource: str,
        trace_id: str = "-",
        metadata: dict | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            actor=actor,
            action=action,
            resource=resource,
            trace_id=trace_id,
            metadata=self.secrets.redact_mapping(metadata or {}),
        )
        return await self._store.save_audit_event(event)

    async def list_audit(self, *, limit: int = 100) -> list[AuditEvent]:
        return await self._store.list_audit_events(limit=limit)

    @staticmethod
    def _to_info(record: APIKey) -> APIKeyInfo:
        return APIKeyInfo(
            id=record.id,
            name=record.name,
            status=record.status,
            role=record.role,
            permissions=record.permissions,
            created_at=record.created_at,
            last_used_at=record.last_used_at,
            metadata=record.metadata,
        )
