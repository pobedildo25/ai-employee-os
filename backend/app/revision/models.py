import enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.quality.models import QualityIssue


class RevisionStatus(str, enum.Enum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    WAITING_USER = "WAITING_USER"


class RevisionRequest(BaseModel):
    source_artifact_id: UUID | str | None = None
    issues: list[QualityIssue] = Field(default_factory=list)
    suggested_changes: list[str] = Field(default_factory=list)
    user_feedback: str | None = None
    revision_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class RevisionResult(BaseModel):
    artifact_id: UUID | str | None = None
    version_id: UUID | str | None = None
    changes_applied: list[str] = Field(default_factory=list)
    summary: str = ""
    status: RevisionStatus = RevisionStatus.COMPLETED
    document_ast: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
