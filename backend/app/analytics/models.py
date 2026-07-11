from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AnalyticsType(str, Enum):
    CLIENT_PERFORMANCE = "CLIENT_PERFORMANCE"
    PROJECT_ANALYSIS = "PROJECT_ANALYSIS"
    DOCUMENT_ANALYSIS = "DOCUMENT_ANALYSIS"
    TEAM_PERFORMANCE = "TEAM_PERFORMANCE"
    BUSINESS_REPORT = "BUSINESS_REPORT"
    MARKETING_ANALYSIS = "MARKETING_ANALYSIS"


class DateRange(BaseModel):
    start: datetime | None = None
    end: datetime | None = None


class AnalyticsInsight(BaseModel):
    category: str
    title: str
    description: str
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)


class AnalyticsRequest(BaseModel):
    analytics_type: AnalyticsType = AnalyticsType.CLIENT_PERFORMANCE
    client_id: UUID | str | None = None
    project_id: UUID | str | None = None
    date_range: DateRange | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    learning_rules: list[dict[str, Any]] = Field(default_factory=list)
    goal: str | None = None


class AnalyticsResult(BaseModel):
    analytics_type: AnalyticsType = AnalyticsType.CLIENT_PERFORMANCE
    summary: str = ""
    metrics: dict[str, Any] = Field(default_factory=dict)
    insights: list[AnalyticsInsight] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    document_ast: dict[str, Any] | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    memory_candidates: list[dict[str, Any]] = Field(default_factory=list)
    analysis_warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AnalyticsDataset(BaseModel):
    """Read-only snapshot assembled from existing system sources."""

    clients: list[dict[str, Any]] = Field(default_factory=list)
    projects: list[dict[str, Any]] = Field(default_factory=list)
    tasks: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    executions: list[dict[str, Any]] = Field(default_factory=list)
    quality_results: list[dict[str, Any]] = Field(default_factory=list)
    revisions: list[dict[str, Any]] = Field(default_factory=list)
    client_intelligence: dict[str, Any] = Field(default_factory=dict)
    learning_rules: list[dict[str, Any]] = Field(default_factory=list)
    sources_used: list[str] = Field(default_factory=list)
