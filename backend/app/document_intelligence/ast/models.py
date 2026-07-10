import enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ASTNodeType(str, enum.Enum):
    DOCUMENT = "document"
    SECTION = "section"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    IMAGE = "image"


class ASTNode(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    node_type: ASTNodeType
    content: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    children: list["ASTNode"] = Field(default_factory=list)


class DocumentAST(BaseModel):
    root: ASTNode
    node_count: int = 0
