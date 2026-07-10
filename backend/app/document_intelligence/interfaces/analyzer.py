from abc import ABC, abstractmethod
from uuid import UUID

from app.document_intelligence.ast.models import DocumentAST
from app.document_intelligence.models import DocumentRepresentation
from app.file_processing.models import ExtractedContent


class DocumentAnalyzerInterface(ABC):
    @abstractmethod
    def analyze(
        self,
        *,
        artifact_id: UUID,
        title: str,
        extracted: ExtractedContent,
    ) -> tuple[DocumentRepresentation, DocumentAST]:
        """Build document representation and AST from extracted content."""
