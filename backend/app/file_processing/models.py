import enum
from typing import Any

from pydantic import BaseModel, Field


class FileCategory(str, enum.Enum):
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    XLSX = "xlsx"
    TEXT = "text"
    IMAGE = "image"
    UNKNOWN = "unknown"


class DetectedFile(BaseModel):
    mime_type: str
    extension: str
    category: FileCategory
    filename: str


class ExtractedContent(BaseModel):
    text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    pages: int | None = None
    tables: list[dict[str, Any]] | None = None
    structure: dict[str, Any] | None = None
