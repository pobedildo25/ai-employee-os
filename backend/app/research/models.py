from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ResearchType(str, Enum):
    MARKET_RESEARCH = "MARKET_RESEARCH"
    COMPETITOR_RESEARCH = "COMPETITOR_RESEARCH"
    COMPANY_RESEARCH = "COMPANY_RESEARCH"
    TREND_ANALYSIS = "TREND_ANALYSIS"
    CONTENT_RESEARCH = "CONTENT_RESEARCH"


class ResearchSource(BaseModel):
    title: str
    url: str | None = None
    source_type: str = "web"
    extracted_content: str = ""
    credibility_score: float = Field(default=0.5, ge=0.0, le=1.0)
    relevance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    freshness_score: float = Field(default=0.5, ge=0.0, le=1.0)
    published_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResearchFinding(BaseModel):
    title: str
    description: str
    source_urls: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)


class ResearchInsight(BaseModel):
    category: str = "general"
    title: str
    description: str
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)


class ResearchRequest(BaseModel):
    query: str
    research_type: ResearchType = ResearchType.MARKET_RESEARCH
    client_id: UUID | str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    constraints: list[str] = Field(default_factory=list)
    learning_rules: list[dict[str, Any]] = Field(default_factory=list)
    max_sources: int = Field(default=8, ge=1, le=50)


class ResearchResult(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    research_type: ResearchType = ResearchType.MARKET_RESEARCH
    query: str = ""
    search_queries: list[str] = Field(default_factory=list)
    summary: str = ""
    sources: list[ResearchSource] = Field(default_factory=list)
    findings: list[ResearchFinding] = Field(default_factory=list)
    insights: list[ResearchInsight] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    document_ast: dict[str, Any] | None = None
    memory_candidates: list[dict[str, Any]] = Field(default_factory=list)
    analysis_warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
