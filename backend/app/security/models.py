from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class APIKeyStatus(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"


class Role(str, Enum):
    ADMIN = "ADMIN"
    USER = "USER"
    SERVICE = "SERVICE"


class Permission(BaseModel):
    resource: str
    action: str

    @property
    def code(self) -> str:
        return f"{self.resource}:{self.action}"

    @classmethod
    def parse(cls, value: str) -> "Permission":
        resource, _, action = value.partition(":")
        if not resource or not action:
            raise ValueError(f"Invalid permission: {value}")
        return cls(resource=resource, action=action)


class APIKey(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    key_hash: str
    status: APIKeyStatus = APIKeyStatus.ACTIVE
    role: Role = Role.USER
    permissions: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    last_used_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class APIKeyCreateResult(BaseModel):
    """Returned once on creation — includes raw api_key; never persisted."""

    id: UUID
    name: str
    api_key: str
    status: APIKeyStatus
    role: Role
    permissions: list[str]
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class APIKeyInfo(BaseModel):
    id: UUID
    name: str
    status: APIKeyStatus
    role: Role
    permissions: list[str]
    created_at: datetime
    last_used_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditEvent(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    actor: str
    action: str
    resource: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now())
    trace_id: str = "-"
    metadata: dict[str, Any] = Field(default_factory=dict)


class SecurityPrincipal(BaseModel):
    actor: str
    api_key_id: UUID | None = None
    role: Role = Role.USER
    permissions: list[str] = Field(default_factory=list)
