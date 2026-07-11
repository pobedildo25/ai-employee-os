from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class LearningScope(str, Enum):
    GLOBAL = "global"
    CLIENT = "client"
    PROJECT = "project"


class LearningSource(str, Enum):
    USER_FEEDBACK = "user_feedback"
    REVISION_REQUEST = "revision_request"
    QUALITY_GATE = "quality_gate"
    EXPLICIT_PREFERENCE = "explicit_preference"


class LearningRule(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    scope: LearningScope = LearningScope.CLIENT
    category: str
    key: str
    value: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    source: LearningSource = LearningSource.USER_FEEDBACK
    client_id: UUID | None = None
    project_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: datetime = Field(default_factory=lambda: datetime.now())


class LearningSignal(BaseModel):
    text: str
    source: LearningSource
    client_id: UUID | None = None
    project_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractedRuleCandidate(BaseModel):
    category: str
    key: str
    value: str
    confidence: float = Field(ge=0.0, le=1.0)
    scope: LearningScope = LearningScope.CLIENT


class RuleExtractionResult(BaseModel):
    rule: ExtractedRuleCandidate | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    should_learn: bool = False
    reason: str | None = None
