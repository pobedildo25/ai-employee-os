"""Render Contract models.

Product entry: ``DocumentRendererService.render(RenderRequest)``.
``OutputFormat.PDF`` exists for the stub path only — do not advertise PDF in
Executive prompt / skill product surface until implemented.
"""

import enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.brand_style.models import BrandProfile
from app.document_intelligence.ast.models import DocumentAST


class OutputFormat(str, enum.Enum):
    DOCX = "docx"
    PPTX = "pptx"
    PDF = "pdf"  # stub only — not offered on product surface


class RenderStatus(str, enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RenderRequest(BaseModel):
    document_structure: DocumentAST
    brand_profile: BrandProfile | None = None
    output_format: OutputFormat
    metadata: dict[str, Any] = Field(default_factory=dict)
    client_id: UUID | None = None
    project_id: UUID | None = None
    name: str | None = None
    source_artifact_id: UUID | None = None
    brand_profile_id: UUID | None = None


class RenderResult(BaseModel):
    artifact_id: UUID | None = None
    file_path: str | None = None
    mime_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: RenderStatus = RenderStatus.COMPLETED
    file_bytes: bytes | None = None
