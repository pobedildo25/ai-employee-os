from typing import Any
from uuid import UUID

from app.document_intelligence.analyzer import DocumentAnalyzer
from app.document_intelligence.ast.models import DocumentAST
from app.document_intelligence.models import AnalysisStatus, DocumentRepresentation
from app.file_processing.models import DetectedFile, ExtractedContent
from app.file_processing.processor import FileProcessor


class DocumentPipeline:
    """Upload → Detect → Extract → Analyze → Build AST → Store Representation."""

    def __init__(
        self,
        processor: FileProcessor | None = None,
        analyzer: DocumentAnalyzer | None = None,
    ) -> None:
        self._processor = processor or FileProcessor()
        self._analyzer = analyzer or DocumentAnalyzer()

    def process_bytes(
        self,
        *,
        artifact_id: UUID,
        title: str,
        data: bytes,
        filename: str,
        mime_type: str | None = None,
    ) -> tuple[DocumentRepresentation, DocumentAST, ExtractedContent, DetectedFile]:
        detected = self._processor.detect(filename, mime_type=mime_type, data=data)
        extracted = self._processor.process_bytes(data, filename, mime_type)
        representation, document_ast = self._analyzer.analyze(
            artifact_id=artifact_id,
            title=title,
            extracted=extracted,
        )
        return representation, document_ast, extracted, detected

    def analyze_extracted(
        self,
        *,
        artifact_id: UUID,
        title: str,
        extracted: ExtractedContent,
    ) -> tuple[DocumentRepresentation, DocumentAST]:
        representation, document_ast = self._analyzer.analyze(
            artifact_id=artifact_id,
            title=title,
            extracted=extracted,
        )
        return representation, document_ast

    def build_artifact_metadata(
        self,
        representation: DocumentRepresentation,
        document_ast: DocumentAST,
        extracted: ExtractedContent,
    ) -> dict[str, Any]:
        return {
            "extracted_text": extracted.text,
            "extraction_metadata": self._build_extraction_metadata(extracted),
            "document_structure": representation.structure,
            "document_type": representation.document_type,
            "ast_reference": representation.ast_reference,
            "analysis_status": representation.analysis_status.value,
            "document_representation": representation.model_dump(mode="json"),
            "document_ast": document_ast.model_dump(mode="json"),
        }

    def _build_extraction_metadata(self, extracted: ExtractedContent) -> dict[str, object]:
        payload: dict[str, object] = dict(extracted.metadata)
        if extracted.pages is not None:
            payload["pages"] = extracted.pages
        if extracted.tables is not None:
            payload["tables"] = extracted.tables
        if extracted.structure is not None:
            payload["structure"] = extracted.structure
        return payload
