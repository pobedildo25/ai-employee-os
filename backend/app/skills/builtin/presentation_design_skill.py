from typing import Any

from app.presentation_design.designer import PresentationDesigner
from app.presentation_design.memory_preparer import prepare_presentation_memory_items
from app.skills.base.skill import BaseSkill
from app.skills.models import Capability, SkillMetadata


class PresentationDesignSkill(BaseSkill):
    """Designs presentation structure/storytelling and emits DocumentAST for PPTX render."""

    def __init__(
        self,
        designer: PresentationDesigner | None = None,
        llm_gateway: Any | None = None,
    ) -> None:
        if designer is None:
            from app.llm.gateway import LLMGateway, create_llm_gateway
            from app.presentation_design.planner import PresentationPlanner

            gateway = llm_gateway or create_llm_gateway()
            if not isinstance(gateway, LLMGateway):
                raise TypeError("llm_gateway must be an LLMGateway instance")
            designer = PresentationDesigner(PresentationPlanner(gateway))
        self._designer = designer
        super().__init__(
            metadata=SkillMetadata(
                id="presentation_design_skill",
                name="presentation_design_skill",
                description="Проектирование структуры и storytelling презентации (AST для PPTX)",
                capabilities=["presentation_design"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "goal": {"type": "string"},
                        "context": {"type": "object"},
                        "brand_profile": {"type": "object"},
                        "presentation_type": {"type": "string"},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "presentation_plan": {"type": "object"},
                        "document_ast": {"type": "object"},
                    },
                },
            ),
            capabilities=[
                Capability(
                    name="presentation_design",
                    description="Структура презентации, storytelling и AST для существующего PPTX renderer",
                    category="presentation",
                ),
            ],
        )

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        goal = payload.get("goal") or payload.get("user_goal") or payload.get("description")
        if not goal:
            return {
                "status": "failed",
                "skill": self.name(),
                "message": "goal is required for presentation design",
                "payload_keys": list(payload.keys()),
            }

        context = dict(payload.get("context") or {})
        learning_rules = list(
            payload.get("learning_rules")
            or context.get("learning_rules")
            or context.get("learning_context")
            or []
        )
        brand_profile = payload.get("brand_profile")

        result = await self._designer.design(
            goal=str(goal),
            context=context,
            brand_profile=brand_profile if isinstance(brand_profile, dict) else brand_profile,
            learning_rules=learning_rules,
            presentation_type=payload.get("presentation_type"),
            trace_id=str(payload.get("trace_id") or "-"),
        )
        memory_items = prepare_presentation_memory_items(
            result,
            client_id=payload.get("client_id"),
            project_id=payload.get("project_id"),
            session_id=payload.get("session_id"),
        )
        meta = result.metadata or {}
        failed = meta.get("status") == "failed" or meta.get("degraded") is True
        return {
            "status": "failed" if failed or not result.document_ast else "completed",
            "skill": self.name(),
            "presentation_plan": result.plan.model_dump(mode="json") if result.plan else None,
            "document_ast": result.document_ast,
            "analysis_warnings": result.analysis_warnings,
            "memory_candidates": [item.model_dump(mode="json") for item in memory_items],
            "metadata": result.metadata,
            "message": "presentation design failed" if failed or not result.document_ast else None,
        }
