from uuid import UUID

from app.document_intelligence.ast.builder import build_document_ast
from app.document_intelligence.ast.models import ASTNode, ASTNodeType, DocumentAST
from app.document_intelligence.interfaces.analyzer import DocumentAnalyzerInterface
from app.document_intelligence.metadata.extractor import extract_document_metadata, infer_document_type
from app.document_intelligence.models import AnalysisStatus, DocumentElement, DocumentRepresentation
from app.document_intelligence.parsers.docx_parser import parse_docx_content
from app.document_intelligence.parsers.pdf_parser import parse_pdf_content
from app.document_intelligence.parsers.pptx_parser import parse_pptx_content
from app.document_intelligence.parsers.xlsx_parser import parse_xlsx_content
from app.file_processing.models import ExtractedContent, FileCategory


class DocumentAnalyzer(DocumentAnalyzerInterface):
    """Builds universal document representation and AST from extracted content."""

    def analyze(
        self,
        *,
        artifact_id: UUID,
        title: str,
        extracted: ExtractedContent,
    ) -> tuple[DocumentRepresentation, DocumentAST]:
        elements, root = self._parse_content(extracted)
        document_ast = build_document_ast(root)
        metadata = extract_document_metadata(title=title, extracted=extracted)
        ast_reference = f"{artifact_id}:ast:{document_ast.root.id}"

        representation = DocumentRepresentation(
            artifact_id=artifact_id,
            title=title or metadata.get("filename", "Untitled"),
            document_type=infer_document_type(extracted),
            structure=self._build_structure_summary(document_ast, extracted),
            elements=elements,
            metadata=metadata,
            extracted_content=extracted.model_dump(),
            analysis_status=AnalysisStatus.COMPLETED,
            ast_reference=ast_reference,
        )
        return representation, document_ast

    def _parse_content(self, extracted: ExtractedContent) -> tuple[list[DocumentElement], ASTNode]:
        category = extracted.metadata.get("category", FileCategory.UNKNOWN.value)
        if category == FileCategory.PDF.value:
            return parse_pdf_content(extracted)
        if category == FileCategory.DOCX.value:
            return parse_docx_content(extracted)
        if category == FileCategory.PPTX.value:
            return parse_pptx_content(extracted)
        if category == FileCategory.XLSX.value:
            return parse_xlsx_content(extracted)
        return self._parse_generic_content(extracted)

    def _parse_generic_content(self, extracted: ExtractedContent) -> tuple[list[DocumentElement], ASTNode]:
        elements: list[DocumentElement] = []
        text = (extracted.text or "").strip()
        section = ASTNode(node_type=ASTNodeType.SECTION, content="Content")
        if text:
            for index, line in enumerate(text.splitlines()):
                if not line.strip():
                    continue
                section.children.append(ASTNode(node_type=ASTNodeType.PARAGRAPH, content=line.strip()))
                elements.append(
                    DocumentElement(
                        element_type="paragraph",
                        content=line.strip(),
                        metadata={"line_index": index + 1},
                        position=len(elements),
                    )
                )
        root = ASTNode(node_type=ASTNodeType.DOCUMENT, content="Document", children=[section])
        return elements, root

    def _build_structure_summary(self, document_ast: DocumentAST, extracted: ExtractedContent) -> dict[str, object]:
        node_types: dict[str, int] = {}
        self._count_node_types(document_ast.root, node_types)
        summary: dict[str, object] = {
            "node_count": document_ast.node_count,
            "node_types": node_types,
            "section_count": node_types.get(ASTNodeType.SECTION.value, 0),
        }
        if extracted.pages is not None:
            summary["pages"] = extracted.pages
        if extracted.tables is not None:
            summary["tables"] = len(extracted.tables)
        return summary

    def _count_node_types(self, node: ASTNode, counts: dict[str, int]) -> None:
        key = node.node_type.value
        counts[key] = counts.get(key, 0) + 1
        for child in node.children:
            self._count_node_types(child, counts)
