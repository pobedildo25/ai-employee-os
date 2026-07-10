from io import BytesIO
from typing import Any

from docx import Document

from app.document_intelligence.ast.models import ASTNode, ASTNodeType
from app.document_renderer.builders.style_applier import StyleApplier
from app.document_renderer.exceptions import RenderValidationError
from app.document_renderer.interfaces.renderer import DocumentRenderer
from app.document_renderer.models import OutputFormat, RenderRequest, RenderResult, RenderStatus


class DocxRenderer(DocumentRenderer):
    MIME_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    def __init__(self, style_applier: StyleApplier | None = None) -> None:
        self._style_applier = style_applier or StyleApplier()

    def validate(self, request: RenderRequest) -> None:
        if request.output_format != OutputFormat.DOCX:
            raise RenderValidationError("DocxRenderer only supports DOCX output")
        if request.document_structure.root.node_type != ASTNodeType.DOCUMENT:
            raise RenderValidationError("Document AST root must be a document node")

    def render(self, request: RenderRequest) -> RenderResult:
        self.validate(request)
        document = Document()
        title = request.metadata.get("title") or request.document_structure.root.content or "Document"

        if document.sections:
            section = document.sections[0]
            self._style_applier.apply_docx_section_layout(section, request.brand_profile)
            self._style_applier.apply_docx_header_footer(section, request.brand_profile, str(title))

        self._render_node(document, request.document_structure.root, request)

        buffer = BytesIO()
        document.save(buffer)
        file_bytes = buffer.getvalue()

        return RenderResult(
            mime_type=self.MIME_TYPE,
            status=RenderStatus.COMPLETED,
            file_bytes=file_bytes,
            metadata={
                "format": OutputFormat.DOCX.value,
                "title": title,
                "node_count": request.document_structure.node_count,
            },
        )

    def _render_node(self, document: Document, node: ASTNode, request: RenderRequest) -> None:
        if node.node_type == ASTNodeType.DOCUMENT:
            for child in node.children:
                self._render_node(document, child, request)
            return

        if node.node_type == ASTNodeType.SECTION:
            for child in node.children:
                self._render_node(document, child, request)
            return

        if node.node_type == ASTNodeType.HEADING:
            paragraph = document.add_paragraph(node.content or "")
            paragraph.style = "Heading 1"
            if paragraph.runs:
                self._style_applier.apply_docx_run_style(
                    paragraph.runs[0],
                    brand_profile=request.brand_profile,
                    heading=True,
                )
            return

        if node.node_type == ASTNodeType.PARAGRAPH:
            paragraph = document.add_paragraph(node.content or "")
            if paragraph.runs:
                self._style_applier.apply_docx_run_style(paragraph.runs[0], brand_profile=request.brand_profile)
            return

        if node.node_type == ASTNodeType.TABLE:
            rows = node.attributes.get("rows") or []
            if rows:
                table = document.add_table(rows=len(rows), cols=len(rows[0]))
                for row_index, row_values in enumerate(rows):
                    for col_index, value in enumerate(row_values):
                        table.rows[row_index].cells[col_index].text = str(value)
            return

        if node.node_type == ASTNodeType.IMAGE:
            image_data = node.attributes.get("image_bytes")
            if image_data:
                document.add_picture(BytesIO(image_data))
            return

        for child in node.children:
            self._render_node(document, child, request)
