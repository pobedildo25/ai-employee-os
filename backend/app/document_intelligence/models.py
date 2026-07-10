import enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AnalysisStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DocumentElement(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    element_type: str
    content: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    position: int = 0


class DocumentRepresentation(BaseModel):
    artifact_id: UUID
    title: str
    document_type: str
    structure: dict[str, Any] = Field(default_factory=dict)
    elements: list[DocumentElement] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    extracted_content: dict[str, Any] = Field(default_factory=dict)
    analysis_status: AnalysisStatus = AnalysisStatus.PENDING
    ast_reference: str | None = None
