from typing import Any

from app.document_intelligence.ast.models import ASTNodeType, DocumentAST
from app.quality.models import IssueSeverity, QualityIssue


class StructureCheck:
    """Universal check: document AST integrity when present."""

    def run(self, *, document_ast: dict[str, Any] | DocumentAST | None) -> list[QualityIssue]:
        if document_ast is None:
            return []

        issues: list[QualityIssue] = []
        try:
            ast = (
                document_ast
                if isinstance(document_ast, DocumentAST)
                else DocumentAST.model_validate(document_ast)
            )
        except Exception as exc:
            return [
                QualityIssue(
                    category="structure",
                    description=f"Document AST is invalid: {exc}",
                    severity=IssueSeverity.CRITICAL,
                    location="document_ast",
                )
            ]

        if ast.root.node_type != ASTNodeType.DOCUMENT:
            issues.append(
                QualityIssue(
                    category="structure",
                    description="AST root must be a document node",
                    severity=IssueSeverity.CRITICAL,
                    location="document_ast.root",
                )
            )
        if ast.node_count < 2:
            issues.append(
                QualityIssue(
                    category="structure",
                    description="Document structure is too shallow",
                    severity=IssueSeverity.MAJOR,
                    location="document_ast",
                )
            )
        if not ast.root.children:
            issues.append(
                QualityIssue(
                    category="structure",
                    description="Document has no sections or content blocks",
                    severity=IssueSeverity.MAJOR,
                    location="document_ast.root.children",
                )
            )
        return issues
