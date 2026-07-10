import enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ReviewStatus(str, enum.Enum):
    PASS = "PASS"
    REVISE = "REVISE"
    ESCALATE = "ESCALATE"


class IssueSeverity(str, enum.Enum):
    INFO = "info"
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"


class QualityIssue(BaseModel):
    category: str
    description: str
    severity: IssueSeverity = IssueSeverity.MINOR
    location: str | None = None


class ReviewResult(BaseModel):
    status: ReviewStatus
    score: float = Field(ge=0.0, le=1.0)
    summary: str
    issues: list[QualityIssue] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RevisionRequest(BaseModel):
    issues: list[QualityIssue] = Field(default_factory=list)
    suggested_changes: list[str] = Field(default_factory=list)
    source_artifact: UUID | str | None = None
