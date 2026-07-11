from app.document_intelligence.ast.builder import build_document_ast
from app.document_intelligence.ast.models import ASTNode, ASTNodeType, DocumentAST
from app.quality.models import IssueSeverity, QualityIssue
from app.strategy.models import StrategyRequest, StrategyResult, StrategySection


class StrategyValidator:
    """Validates strategy requests/results and strategy-oriented AST."""

    def validate_request(self, request: StrategyRequest) -> list[str]:
        errors: list[str] = []
        if not request.goal.strip():
            errors.append("goal is required")
        return errors

    def validate_result(self, result: StrategyResult) -> list[str]:
        errors: list[str] = []
        if not result.summary.strip() and not result.insights:
            errors.append("summary or insights are required")
        if not result.recommendations:
            errors.append("recommendations are required")
        return errors

    def quality_issues(
        self,
        *,
        request: StrategyRequest | None = None,
        result: StrategyResult | None = None,
        document_ast: DocumentAST | dict | None = None,
    ) -> list[QualityIssue]:
        issues: list[QualityIssue] = []
        if request is not None:
            for error in self.validate_request(request):
                issues.append(
                    QualityIssue(
                        category="content",
                        description=error,
                        severity=IssueSeverity.MAJOR,
                        location="strategy_request",
                    )
                )
        if result is not None:
            for error in self.validate_result(result):
                issues.append(
                    QualityIssue(
                        category="content",
                        description=error,
                        severity=IssueSeverity.MAJOR,
                        location="strategy_result",
                    )
                )
            if not result.insights:
                issues.append(
                    QualityIssue(
                        category="content",
                        description="strategy has no insights/conclusions",
                        severity=IssueSeverity.MAJOR,
                        location="strategy_result.insights",
                    )
                )

        if document_ast is not None:
            ast = (
                document_ast
                if isinstance(document_ast, DocumentAST)
                else DocumentAST.model_validate(document_ast)
            )
            if ast.root.node_type != ASTNodeType.DOCUMENT:
                issues.append(
                    QualityIssue(
                        category="structure",
                        description="Strategy AST root must be DOCUMENT",
                        severity=IssueSeverity.CRITICAL,
                        location="document_ast",
                    )
                )
            sections = [c for c in ast.root.children if c.node_type == ASTNodeType.SECTION]
            if len(sections) < 2:
                issues.append(
                    QualityIssue(
                        category="structure",
                        description="Strategy document structure is invalid (need sections)",
                        severity=IssueSeverity.MAJOR,
                        location="document_ast",
                    )
                )
        return issues


def result_to_document_ast(result: StrategyResult, *, title: str | None = None) -> DocumentAST:
    """Map StrategyResult to DocumentAST for existing Document Creation / Renderer."""
    sections = list(result.sections)
    if not sections:
        sections = _default_sections(result)

    children: list[ASTNode] = []
    for section in sections:
        children.append(_section_node(section))

    root = ASTNode(
        node_type=ASTNodeType.DOCUMENT,
        content=title or f"{result.strategy_type.value.replace('_', ' ').title()} Report",
        attributes={
            "document_type": "docx",
            "strategy_type": result.strategy_type.value,
            "kind": "strategy",
        },
        children=children,
    )
    return build_document_ast(root)


def _default_sections(result: StrategyResult) -> list[StrategySection]:
    sections: list[StrategySection] = [
        StrategySection(
            title="Executive Summary",
            paragraphs=[result.summary] if result.summary else ["Strategy overview pending."],
        ),
        StrategySection(
            title="Market Analysis",
            paragraphs=[
                f"{insight.title}: {insight.description}"
                for insight in result.insights
                if insight.category in {"market", "audience", "competitor", "general"}
            ]
            or [insight.description for insight in result.insights[:3]]
            or ["Analysis details to be refined."],
        ),
        StrategySection(
            title="Strategy",
            paragraphs=_framework_paragraphs(result.framework_data)
            or [insight.description for insight in result.insights]
            or ["Strategic direction to be refined."],
        ),
        StrategySection(
            title="Recommendations",
            paragraphs=result.recommendations or ["No recommendations yet."],
        ),
        StrategySection(
            title="Next Steps",
            paragraphs=result.recommendations[-2:] if len(result.recommendations) >= 2 else result.recommendations
            or ["Define owners and timeline."],
        ),
    ]
    return sections


def _framework_paragraphs(framework_data: dict) -> list[str]:
    paragraphs: list[str] = []
    for key, value in framework_data.items():
        label = str(key).replace("_", " ").title()
        if isinstance(value, list):
            if value:
                paragraphs.append(f"{label}: " + "; ".join(str(v) for v in value))
        elif isinstance(value, str) and value.strip():
            paragraphs.append(f"{label}: {value}")
    return paragraphs


def _section_node(section: StrategySection) -> ASTNode:
    children: list[ASTNode] = [
        ASTNode(node_type=ASTNodeType.HEADING, content=section.title, attributes={}),
    ]
    for paragraph in section.paragraphs:
        children.append(
            ASTNode(node_type=ASTNodeType.PARAGRAPH, content=paragraph, attributes={})
        )
    return ASTNode(
        node_type=ASTNodeType.SECTION,
        content=section.title,
        attributes={},
        children=children,
    )
