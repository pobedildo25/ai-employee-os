from typing import Any

from app.quality.gate import QualityGate
from app.quality.memory_preparer import prepare_quality_memory_items
from app.quality.reviewer import ReviewerAgent
from app.skills.base.skill import BaseSkill
from app.skills.models import Capability, SkillMetadata


class QualityReviewSkill(BaseSkill):
    """Reviews artifact output quality and returns ReviewResult."""

    def __init__(
        self,
        gate: QualityGate | None = None,
        reviewer: ReviewerAgent | None = None,
    ) -> None:
        if gate is None:
            from app.llm.gateway import LLMGateway, create_llm_gateway

            gateway = create_llm_gateway()
            agent = reviewer or ReviewerAgent(gateway)
            gate = QualityGate(agent)
        self._gate = gate
        super().__init__(
            metadata=SkillMetadata(
                id="quality_review_skill",
                name="quality_review_skill",
                description="Универсальная проверка качества результата",
                capabilities=["quality_review"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "user_goal": {"type": "string"},
                        "render_result": {"type": "object"},
                        "document_ast": {"type": "object"},
                        "brand_profile": {"type": "object"},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "review_result": {"type": "object"},
                    },
                },
            ),
            capabilities=[
                Capability(
                    name="quality_review",
                    description="Оценка качества созданного результата",
                    category="quality",
                ),
            ],
        )

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        context = {
            "user_goal": payload.get("user_goal") or payload.get("goal") or "",
            "understanding": payload.get("understanding") or {},
            "decision": payload.get("decision") or {},
            "execution_context": payload.get("context") or payload.get("execution_context") or {},
            "document_ast": payload.get("document_ast"),
            "brand_profile": payload.get("brand_profile"),
            "render_result": payload.get("render_result") or payload.get("artifact"),
        }

        review_result, revision_request = await self._gate.evaluate(
            context,
            trace_id=str(payload.get("trace_id") or "-"),
        )
        memory_items = prepare_quality_memory_items(
            review_result,
            user_goal=str(context["user_goal"]),
            client_id=payload.get("client_id"),
            project_id=payload.get("project_id"),
            session_id=payload.get("session_id"),
        )

        meta = review_result.metadata or {}
        degraded = bool(meta.get("degraded")) or str(meta.get("status") or "").lower() == "failed"
        skill_status = "failed" if degraded else "completed"

        return {
            "status": skill_status,
            "skill": self.name(),
            "review_result": review_result.model_dump(mode="json"),
            "revision_request": revision_request.model_dump(mode="json") if revision_request else None,
            "memory_candidates": [item.model_dump(mode="json") for item in memory_items],
        }
