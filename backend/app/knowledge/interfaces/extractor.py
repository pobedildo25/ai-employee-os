from abc import ABC, abstractmethod
from typing import Any

from app.brand_style.models import BrandProfile
from app.document_intelligence.ast.models import DocumentAST
from app.document_intelligence.models import DocumentRepresentation
from app.knowledge.models import KnowledgeItem


class KnowledgeExtractorInterface(ABC):
    @abstractmethod
    async def extract(
        self,
        *,
        representation: DocumentRepresentation,
        document_ast: DocumentAST | None = None,
        brand_profile: BrandProfile | None = None,
        context: dict[str, Any] | None = None,
        trace_id: str = "-",
    ) -> list[KnowledgeItem]:
        """Extract universal knowledge items from a document."""
