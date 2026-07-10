from app.document_intelligence.ast.models import ASTNode, DocumentAST


def build_document_ast(root: ASTNode) -> DocumentAST:
    return DocumentAST(root=root, node_count=_count_nodes(root))


def _count_nodes(node: ASTNode) -> int:
    return 1 + sum(_count_nodes(child) for child in node.children)
