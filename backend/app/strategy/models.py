from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class StrategyType(str, Enum):
    MARKETING_STRATEGY = "marketing_strategy"
    SWOT_ANALYSIS = "swot_analysis"
    POSITIONING = "positioning"
    GO_TO_MARKET = "go_to_market"
    COMPETITOR_ANALYSIS = "competitor_analysis"
    CAMPAIGN_PLAN = "campaign_plan"


class StrategyInsight(BaseModel):
    category: str
    title: str
    description: str
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)


class StrategyRequest(BaseModel):
    goal: str
    client_context: dict[str, Any] = Field(default_factory=dict)
    project_context: dict[str, Any] = Field(default_factory=dict)
    audience: str | None = None
    constraints: list[str] = Field(default_factory=list)
    strategy_type: StrategyType | None = None
    learning_rules: list[dict[str, Any]] = Field(default_factory=list)
    brand_profile: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class StrategySection(BaseModel):
    title: str
    paragraphs: list[str] = Field(default_factory=list)


class StrategyResult(BaseModel):
    strategy_type: StrategyType = StrategyType.MARKETING_STRATEGY
    summary: str = ""
    insights: list[StrategyInsight] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    sections: list[StrategySection] = Field(default_factory=list)
    framework_data: dict[str, Any] = Field(default_factory=dict)
    document_ast: dict[str, Any] | None = None
    memory_candidates: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    missing_information: list[str] = Field(default_factory=list)
    analysis_warnings: list[str] = Field(default_factory=list)
