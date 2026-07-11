from typing import Any

from app.brand_style.models import BrandProfile
from app.presentation_design.analyzer import PresentationAnalyzer
from app.presentation_design.interfaces.designer import PresentationDesignerInterface
from app.presentation_design.models import PresentationDesignResult
from app.presentation_design.planner import PresentationPlanner
from app.presentation_design.validators.presentation_validator import (
    PresentationValidator,
    plan_to_document_ast,
)


class PresentationDesigner(PresentationDesignerInterface):
    """Plans storytelling structure and emits DocumentAST for PPTX renderer."""

    def __init__(
        self,
        planner: PresentationPlanner,
        analyzer: PresentationAnalyzer | None = None,
        validator: PresentationValidator | None = None,
    ) -> None:
        self._planner = planner
        self._analyzer = analyzer or PresentationAnalyzer()
        self._validator = validator or PresentationValidator()

    async def design(
        self,
        *,
        goal: str,
        context: dict[str, Any] | None = None,
        brand_profile: dict[str, Any] | BrandProfile | None = None,
        learning_rules: list[dict[str, Any]] | None = None,
        presentation_type: str | None = None,
        trace_id: str = "-",
    ) -> PresentationDesignResult:
        context = context or {}
        brand_dict: dict[str, Any] | None
        if isinstance(brand_profile, BrandProfile):
            brand_dict = brand_profile.model_dump(mode="json")
        else:
            brand_dict = brand_profile

        learning = learning_rules or list(context.get("learning_rules") or context.get("learning_context") or [])

        plan = await self._planner.plan(
            goal=goal,
            context=context,
            brand_profile=brand_dict,
            learning_rules=learning,
            presentation_type=presentation_type or context.get("presentation_type"),
            trace_id=trace_id,
        )
        if brand_dict and brand_dict.get("id") and plan.brand_profile_id is None:
            plan.brand_profile_id = brand_dict.get("id")

        errors = self._validator.validate_plan(plan)
        if errors:
            return PresentationDesignResult(
                plan=plan,
                document_ast=None,
                analysis_warnings=errors,
                missing_information=errors,
                metadata={"status": "invalid"},
            )

        warnings = self._analyzer.analyze(plan)
        document_ast = plan_to_document_ast(plan, brand_profile=brand_dict)
        return PresentationDesignResult(
            plan=plan,
            document_ast=document_ast.model_dump(mode="json"),
            analysis_warnings=warnings,
            metadata={
                "status": "ready",
                "document_type": "pptx",
                "slide_count": len(plan.slides),
                "presentation_type": plan.presentation_type.value,
            },
        )
