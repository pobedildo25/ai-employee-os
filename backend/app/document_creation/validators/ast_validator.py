from app.document_intelligence.ast.models import ASTNode, ASTNodeType, DocumentAST
from app.document_creation.models import DocumentCreationResult


class ASTValidationError(Exception):
    """Raised when generated AST fails validation."""


class ASTValidator:
    ALLOWED_TYPES = {
        ASTNodeType.DOCUMENT,
        ASTNodeType.SECTION,
        ASTNodeType.HEADING,
        ASTNodeType.PARAGRAPH,
        ASTNodeType.TABLE,
        ASTNodeType.IMAGE,
    }

    def validate(self, document_ast: DocumentAST) -> None:
        if document_ast.root.node_type != ASTNodeType.DOCUMENT:
            raise ASTValidationError("AST root must be a document node")
        if document_ast.node_count < 2:
            raise ASTValidationError("AST must contain more than a root node")
        self._validate_node(document_ast.root)

    def _validate_node(self, node: ASTNode) -> None:
        if node.node_type not in self.ALLOWED_TYPES:
            raise ASTValidationError(f"Unsupported node type: {node.node_type}")
        for child in node.children:
            self._validate_node(child)

    def detect_missing_information(self, result: DocumentCreationResult) -> list[str]:
        if result.missing_information:
            return result.missing_information
        if result.document_ast is None:
            return ["document structure was not generated"]
        return []
