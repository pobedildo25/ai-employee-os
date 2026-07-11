from app.document_intelligence.ast.builder import build_document_ast
from app.document_intelligence.ast.models import ASTNode, ASTNodeType, DocumentAST
from app.presentation_design.layouts import layout_rules
from app.presentation_design.models import PresentationPlan, SlidePlan
from app.quality.models import IssueSeverity, QualityIssue


class PresentationValidator:
    """Validates presentation plans and presentation-oriented AST."""

    def validate_plan(self, plan: PresentationPlan) -> list[str]:
        errors: list[str] = []
        if not plan.title.strip():
            errors.append("title is required")
        if not plan.slides:
            errors.append("slides are required")
        orders = [slide.order for slide in plan.slides]
        if len(orders) != len(set(orders)):
            errors.append("slide order values must be unique")
        return errors

    def quality_issues(
        self,
        *,
        plan: PresentationPlan | None = None,
        document_ast: DocumentAST | dict | None = None,
        brand_profile: dict | None = None,
    ) -> list[QualityIssue]:
        issues: list[QualityIssue] = []
        if plan is not None:
            for error in self.validate_plan(plan):
                issues.append(
                    QualityIssue(
                        category="structure",
                        description=error,
                        severity=IssueSeverity.MAJOR,
                        location="presentation_plan",
                    )
                )
            if len(plan.slides) < layout_rules.MIN_RECOMMENDED_SLIDES:
                issues.append(
                    QualityIssue(
                        category="structure",
                        description="slide_count below recommended minimum",
                        severity=IssueSeverity.MINOR,
                        location="presentation_plan.slides",
                    )
                )
            total_chars = sum(
                len(block.text) for slide in plan.slides for block in slide.content_blocks
            )
            if layout_rules.text_density_score(total_chars, len(plan.slides) or 1) > 0.9:
                issues.append(
                    QualityIssue(
                        category="content",
                        description="text_density is too high for slides",
                        severity=IssueSeverity.MAJOR,
                        location="presentation_plan",
                    )
                )

        if document_ast is not None:
            ast = (
                document_ast
                if isinstance(document_ast, DocumentAST)
                else DocumentAST.model_validate(document_ast)
            )
            sections = [c for c in ast.root.children if c.node_type == ASTNodeType.SECTION]
            if not sections:
                issues.append(
                    QualityIssue(
                        category="structure",
                        description="Presentation AST has no SECTION slides",
                        severity=IssueSeverity.CRITICAL,
                        location="document_ast",
                    )
                )

        if brand_profile is not None and not (
            brand_profile.get("colors") or brand_profile.get("typography")
        ):
            issues.append(
                QualityIssue(
                    category="style",
                    description="brand_style compatibility: missing colors/typography",
                    severity=IssueSeverity.MINOR,
                    location="brand_profile",
                )
            )
        return issues


def plan_to_document_ast(
    plan: PresentationPlan,
    *,
    brand_profile: dict | None = None,
) -> DocumentAST:
    """Map PresentationPlan slides to DocumentAST SECTIONs for PPTX renderer."""
    children: list[ASTNode] = []
    for slide in sorted(plan.slides, key=lambda item: item.order):
        children.append(_slide_to_section(slide))

    attributes: dict = {
        "document_type": "pptx",
        "presentation_type": plan.presentation_type.value,
        "audience": plan.audience,
    }
    if brand_profile:
        attributes["brand"] = {
            "colors": brand_profile.get("colors"),
            "typography": brand_profile.get("typography"),
            "layout_rules": brand_profile.get("layout_rules"),
        }
        if brand_profile.get("id"):
            attributes["brand_profile_id"] = brand_profile.get("id")

    root = ASTNode(
        node_type=ASTNodeType.DOCUMENT,
        content=plan.title,
        attributes=attributes,
        children=children,
    )
    return build_document_ast(root)


def _slide_to_section(slide: SlidePlan) -> ASTNode:
    children: list[ASTNode] = [
        ASTNode(node_type=ASTNodeType.HEADING, content=slide.title, attributes={}),
    ]
    for block in slide.content_blocks:
        children.append(
            ASTNode(
                node_type=ASTNodeType.PARAGRAPH,
                content=block.text,
                attributes={"kind": block.kind},
            )
        )
    return ASTNode(
        node_type=ASTNodeType.SECTION,
        content=slide.title,
        attributes={
            "slide_type": slide.slide_type.value,
            "purpose": slide.purpose,
            "visual_notes": slide.visual_notes,
            "order": slide.order,
        },
        children=children,
    )
