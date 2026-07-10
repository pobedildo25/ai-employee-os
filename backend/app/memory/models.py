import enum
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class MemoryType(str, enum.Enum):
    SHORT_TERM = "SHORT_TERM"
    FACT = "FACT"
    PREFERENCE = "PREFERENCE"
    DECISION = "DECISION"
    KNOWLEDGE = "KNOWLEDGE"


class MemoryItem(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    type: MemoryType
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    source: str = "system"
    client_id: UUID | None = None
    project_id: UUID | None = None
    session_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    expires_at: datetime | None = None


class MemorySearchQuery(BaseModel):
    query: str | None = None
    memory_types: list[MemoryType] | None = None
    client_id: UUID | None = None
    project_id: UUID | None = None
    session_id: str | None = None
    limit: int = Field(default=10, ge=1, le=100)
