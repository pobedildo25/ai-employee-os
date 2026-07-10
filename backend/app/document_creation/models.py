from typing import Any

from pydantic import BaseModel, Field

from app.brand_style.models import BrandProfile
from app.document_intelligence.ast.models import DocumentAST


class DocumentCreationRequest(BaseModel):
    user_goal: str
    context: dict[str, Any] = Field(default_factory=dict)
    brand_profile: BrandProfile | None = None
    document_type: str | None = None
    requirements: list[str] = Field(default_factory=list)


class DocumentCreationResult(BaseModel):
    document_ast: DocumentAST | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    missing_information: list[str] = Field(default_factory=list)
