import logging
from typing import Any

from app.agent_runtime.state.models import AgentState
from app.presentation_design.designer import PresentationDesigner

logger = logging.getLogger(__name__)

PRESENTATION_DESIGN_NODE = "presentation_design"


class PresentationDesignNode:
    """LangGraph-ready node — prepare plan+AST before DocumentRenderSkill."""

    name = PRESENTATION_DESIGN_NODE

    def __init__(self, designer: PresentationDesigner) -> None:
        self._designer = designer

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        context = state.get("execution_context") or state.get("context") or {}
        metadata = state.get("metadata") or {}
        goal = (
            metadata.get("presentation_goal")
            or context.get("presentation_goal")
            or state.get("user_input")
            or ""
        )
        brand = metadata.get("brand_profile") or context.get("brand_profile")
        learning = context.get("learning_context") or context.get("learning_rules") or []

        result = await self._designer.design(
            goal=str(goal),
            context=dict(context) if isinstance(context, dict) else {},
            brand_profile=brand if isinstance(brand, dict) else None,
            learning_rules=list(learning) if isinstance(learning, list) else [],
            presentation_type=metadata.get("presentation_type") or context.get("presentation_type"),
            trace_id=state.get("trace_id", "-"),
        )

        update: dict[str, Any] = {
            "current_step": self.name,
            "status": "presentation_designed" if result.document_ast else "presentation_design_incomplete",
            "presentation_plan": result.plan.model_dump(mode="json") if result.plan else None,
            "document_ast": result.document_ast,
            "document_creation_result": {
                "document_ast": result.document_ast,
                "metadata": {**result.metadata, "document_type": "pptx"},
                "missing_information": result.missing_information,
            },
        }
        logger.info(
            "presentation design node | execution_id=%s slides=%s",
            state.get("execution_id", "-"),
            (result.plan and len(result.plan.slides)) or 0,
        )
        return update
