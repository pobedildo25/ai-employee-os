from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class IntelligenceSignal(BaseModel):
    category: str
    key: str
    value: str
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    source: str | None = None


class ClientProfile(BaseModel):
    client_id: UUID | str
    summary: str = ""
    industry: str | None = None
    services: list[str] = Field(default_factory=list)
    preferences: dict[str, Any] = Field(default_factory=dict)
    communication_style: dict[str, Any] = Field(default_factory=dict)
    brand_profile: dict[str, Any] | None = None
    previous_projects: list[dict[str, Any]] = Field(default_factory=list)
    successful_patterns: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    signals: list[IntelligenceSignal] = Field(default_factory=list)
    sources_used: list[str] = Field(default_factory=list)


class ClientIntelligenceSources(BaseModel):
    """Aggregated existing-system fragments — not a new memory store."""

    client_id: UUID | str
    client_context: dict[str, Any] = Field(default_factory=dict)
    memory_items: list[dict[str, Any]] = Field(default_factory=list)
    knowledge_items: list[dict[str, Any]] = Field(default_factory=list)
    learning_rules: list[dict[str, Any]] = Field(default_factory=list)
    workspace: dict[str, Any] = Field(default_factory=dict)
    projects: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    brand_profiles: list[dict[str, Any]] = Field(default_factory=list)
    past_tasks: list[dict[str, Any]] = Field(default_factory=list)
    execution_context: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ClientIntelligenceResult(BaseModel):
    profile: ClientProfile
    memory_candidates: list[dict[str, Any]] = Field(default_factory=list)
    analysis_warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
