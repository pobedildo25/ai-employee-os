from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class BrandProfile(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    client_id: UUID | None = None
    name: str = "Brand Profile"
    typography: dict[str, Any] = Field(default_factory=dict)
    colors: dict[str, Any] = Field(default_factory=dict)
    layout_rules: dict[str, Any] = Field(default_factory=dict)
    document_rules: dict[str, Any] = Field(default_factory=dict)
    visual_elements: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_artifacts: list[UUID] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now())
