from abc import ABC, abstractmethod
from uuid import UUID

from app.security.models import APIKey, AuditEvent


class SecurityStore(ABC):
    @abstractmethod
    async def save_api_key(self, api_key: APIKey) -> APIKey:
        raise NotImplementedError

    @abstractmethod
    async def get_api_key(self, key_id: UUID) -> APIKey | None:
        raise NotImplementedError

    @abstractmethod
    async def get_api_key_by_hash(self, key_hash: str) -> APIKey | None:
        raise NotImplementedError

    @abstractmethod
    async def list_api_keys(self, *, limit: int = 100) -> list[APIKey]:
        raise NotImplementedError

    @abstractmethod
    async def save_audit_event(self, event: AuditEvent) -> AuditEvent:
        raise NotImplementedError

    @abstractmethod
    async def list_audit_events(self, *, limit: int = 100) -> list[AuditEvent]:
        raise NotImplementedError
