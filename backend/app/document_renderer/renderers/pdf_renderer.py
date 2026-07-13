from app.document_intelligence.ast.models import ASTNode, ASTNodeType, DocumentAST
from app.document_renderer.exceptions import RenderValidationError, UnsupportedFormatError
from app.document_renderer.interfaces.renderer import DocumentRenderer
from app.document_renderer.models import OutputFormat, RenderRequest, RenderResult


class PdfRenderer(DocumentRenderer):
    """PDF stub — not offered on product surface; raises if somehow called."""

    def validate(self, request: RenderRequest) -> None:
        if request.output_format != OutputFormat.PDF:
            raise RenderValidationError("PdfRenderer only supports PDF output")

    def render(self, request: RenderRequest) -> RenderResult:
        self.validate(request)
        raise UnsupportedFormatError(
            "PDF rendering is not implemented; use docx or pptx"
        )
