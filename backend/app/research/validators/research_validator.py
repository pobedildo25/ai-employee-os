from app.document_intelligence.ast.builder import build_document_ast
from app.document_intelligence.ast.models import ASTNode, ASTNodeType, DocumentAST
from app.quality.models import IssueSeverity, QualityIssue
from app.research.models import ResearchRequest, ResearchResult


class ResearchValidator:
    def validate_request(self, request: ResearchRequest) -> list[str]:
        errors: list[str] = []
        if not request.query.strip():
            errors.append("query is required")
        return errors

    def validate_result(self, result: ResearchResult) -> list[str]:
        errors: list[str] = []
        if not result.sources:
            errors.append("sources are required")
        if not result.findings:
            errors.append("findings are required")
        if result.confidence < 0 or result.confidence > 1:
            errors.append("confidence is invalid")
        if result.sources and not any(s.url or s.title for s in result.sources):
            errors.append("source tracking is incomplete")
        return errors

    def quality_issues(self, result: ResearchResult | None) -> list[QualityIssue]:
        if result is None:
            return [
                QualityIssue(
                    category="content",
                    description="research result missing",
                    severity=IssueSeverity.MAJOR,
                    location="research_result",
                )
            ]
        issues: list[QualityIssue] = []
        for error in self.validate_result(result):
            severity = IssueSeverity.MINOR if "confidence" in error else IssueSeverity.MAJOR
            issues.append(
                QualityIssue(
                    category="content",
                    description=error,
                    severity=severity,
                    location="research_result",
                )
            )
        return issues


def result_to_document_ast(result: ResearchResult, *, title: str | None = None) -> DocumentAST:
    source_lines = [
        f"{s.title}" + (f" — {s.url}" if s.url else "")
        for s in result.sources
    ] or ["No sources collected."]
    finding_lines = [f"{f.title}: {f.description}" for f in result.findings] or ["No findings."]
    insight_lines = [f"{i.title}: {i.description}" for i in result.insights] or ["No insights."]
    sections = [
        _section("Executive Summary", [result.summary] if result.summary else ["Research summary pending."]),
        _section("Sources", source_lines),
        _section("Findings", finding_lines),
        _section("Market Insights", insight_lines),
        _section(
            "Recommendations",
            result.recommendations or ["Feed research into strategy_analysis."],
        ),
    ]
    root = ASTNode(
        node_type=ASTNodeType.DOCUMENT,
        content=title or f"{result.research_type.value.replace('_', ' ').title()} Report",
        attributes={
            "document_type": "docx",
            "kind": "research",
            "research_type": result.research_type.value,
            "research_id": str(result.id),
        },
        children=sections,
    )
    return build_document_ast(root)


def _section(title: str, paragraphs: list[str]) -> ASTNode:
    children: list[ASTNode] = [ASTNode(node_type=ASTNodeType.HEADING, content=title, attributes={})]
    for paragraph in paragraphs:
        children.append(ASTNode(node_type=ASTNodeType.PARAGRAPH, content=paragraph, attributes={}))
    return ASTNode(node_type=ASTNodeType.SECTION, content=title, attributes={}, children=children)
