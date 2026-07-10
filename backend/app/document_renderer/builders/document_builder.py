from app.document_intelligence.ast.models import ASTNode, ASTNodeType, DocumentAST
from app.document_renderer.exceptions import RenderValidationError


class DocumentBuilder:
    """Builds and validates document AST structures for rendering."""

    def validate_ast(self, document_ast: DocumentAST) -> None:
        if document_ast.root.node_type != ASTNodeType.DOCUMENT:
            raise RenderValidationError("AST root must be a document node")
        if document_ast.node_count <= 0:
            raise RenderValidationError("AST must contain at least one node")

    def count_nodes_by_type(self, document_ast: DocumentAST) -> dict[str, int]:
        counts: dict[str, int] = {}
        self._count_node(document_ast.root, counts)
        return counts

    def extract_sections(self, document_ast: DocumentAST) -> list[ASTNode]:
        return [
            child
            for child in document_ast.root.children
            if child.node_type == ASTNodeType.SECTION
        ]

    def _count_node(self, node: ASTNode, counts: dict[str, int]) -> None:
        key = node.node_type.value
        counts[key] = counts.get(key, 0) + 1
        for child in node.children:
            self._count_node(child, counts)
