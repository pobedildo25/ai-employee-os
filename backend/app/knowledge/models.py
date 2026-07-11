from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class KnowledgeItem(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    client_id: UUID | None = None
    title: str
    category: str = "general"
    content: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    source_artifact_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now())


class KnowledgeMigrationResult(BaseModel):
    processed_artifacts: list[UUID] = Field(default_factory=list)
    extracted_items: list[KnowledgeItem] = Field(default_factory=list)
    brand_profiles: list[dict[str, Any]] = Field(default_factory=list)
    memory_candidates: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
