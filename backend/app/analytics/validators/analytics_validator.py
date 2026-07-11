from app.document_intelligence.ast.builder import build_document_ast
from app.document_intelligence.ast.models import ASTNode, ASTNodeType, DocumentAST
from app.quality.models import IssueSeverity, QualityIssue
from app.analytics.models import AnalyticsRequest, AnalyticsResult


class AnalyticsValidator:
    def validate_request(self, request: AnalyticsRequest) -> list[str]:
        errors: list[str] = []
        if request.analytics_type is None:
            errors.append("analytics_type is required")
        return errors

    def validate_result(self, result: AnalyticsResult) -> list[str]:
        errors: list[str] = []
        if not result.metrics:
            errors.append("metrics are required")
        if not result.insights:
            errors.append("insights are required")
        if not result.recommendations:
            errors.append("recommendations are required")
        if result.confidence < 0 or result.confidence > 1:
            errors.append("confidence is invalid")
        return errors

    def quality_issues(self, result: AnalyticsResult | None) -> list[QualityIssue]:
        if result is None:
            return [
                QualityIssue(
                    category="content",
                    description="analytics result missing",
                    severity=IssueSeverity.MAJOR,
                    location="analytics_result",
                )
            ]
        issues: list[QualityIssue] = []
        for error in self.validate_result(result):
            severity = IssueSeverity.MAJOR
            if "confidence" in error:
                severity = IssueSeverity.MINOR
            issues.append(
                QualityIssue(
                    category="content",
                    description=error,
                    severity=severity,
                    location="analytics_result",
                )
            )
        return issues


def result_to_document_ast(result: AnalyticsResult, *, title: str | None = None) -> DocumentAST:
    sections = [
        _section(
            "Executive Summary",
            [result.summary] if result.summary else ["Analytics summary pending."],
        ),
        _section("Metrics", _metrics_paragraphs(result.metrics)),
        _section(
            "Insights",
            [f"{item.title}: {item.description}" for item in result.insights]
            or ["No insights available."],
        ),
        _section(
            "Recommendations",
            result.recommendations or ["No recommendations yet."],
        ),
        _section(
            "Next Steps",
            result.recommendations[-2:]
            if len(result.recommendations) >= 2
            else result.recommendations
            or ["Validate findings with stakeholders."],
        ),
    ]
    root = ASTNode(
        node_type=ASTNodeType.DOCUMENT,
        content=title or f"{result.analytics_type.value.replace('_', ' ').title()} Report",
        attributes={
            "document_type": "docx",
            "kind": "analytics",
            "analytics_type": result.analytics_type.value,
        },
        children=sections,
    )
    return build_document_ast(root)


def _metrics_paragraphs(metrics: dict) -> list[str]:
    paragraphs: list[str] = []
    for group, values in metrics.items():
        if isinstance(values, dict):
            parts = ", ".join(f"{k}={v}" for k, v in values.items())
            paragraphs.append(f"{str(group).title()}: {parts}")
        else:
            paragraphs.append(f"{group}: {values}")
    return paragraphs or ["No metrics available."]


def _section(title: str, paragraphs: list[str]) -> ASTNode:
    children: list[ASTNode] = [
        ASTNode(node_type=ASTNodeType.HEADING, content=title, attributes={}),
    ]
    for paragraph in paragraphs:
        children.append(ASTNode(node_type=ASTNodeType.PARAGRAPH, content=paragraph, attributes={}))
    return ASTNode(node_type=ASTNodeType.SECTION, content=title, attributes={}, children=children)
