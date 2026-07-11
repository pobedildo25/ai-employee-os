from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PresentationType(str, Enum):
    BUSINESS = "business"
    SALES = "sales"
    MARKETING = "marketing"
    PITCH = "pitch"
    CUSTOM = "custom"


class SlideType(str, Enum):
    TITLE = "TITLE"
    PROBLEM = "PROBLEM"
    SOLUTION = "SOLUTION"
    PROCESS = "PROCESS"
    FEATURES = "FEATURES"
    BENEFITS = "BENEFITS"
    COMPARISON = "COMPARISON"
    CASE_STUDY = "CASE_STUDY"
    DATA = "DATA"
    TIMELINE = "TIMELINE"
    TEAM = "TEAM"
    OFFER = "OFFER"
    CTA = "CTA"


class ContentBlock(BaseModel):
    kind: str = "paragraph"
    text: str


class SlidePlan(BaseModel):
    order: int = Field(ge=0)
    slide_type: SlideType
    title: str
    purpose: str = ""
    content_blocks: list[ContentBlock] = Field(default_factory=list)
    visual_notes: str | None = None


class PresentationPlan(BaseModel):
    title: str
    goal: str
    audience: str | None = None
    presentation_type: PresentationType = PresentationType.CUSTOM
    slides: list[SlidePlan] = Field(default_factory=list)
    brand_profile_id: UUID | str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PresentationDesignResult(BaseModel):
    plan: PresentationPlan | None = None
    document_ast: dict[str, Any] | None = None
    analysis_warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    missing_information: list[str] = Field(default_factory=list)
