from typing import Any

from app.skills.base.skill import BaseSkill
from app.skills.models import Capability, SkillMetadata
from app.strategy.memory_preparer import prepare_strategy_memory_items
from app.strategy.models import StrategyRequest, StrategyType
from app.strategy.strategist import StrategyStrategist


class StrategySkill(BaseSkill):
    """Marketing / business strategy analysis with DocumentAST for existing renderer."""

    def __init__(
        self,
        strategist: StrategyStrategist | None = None,
        llm_gateway: Any | None = None,
    ) -> None:
        if strategist is None:
            from app.llm.gateway import LLMGateway, create_llm_gateway
            from app.strategy.planner import StrategyPlanner

            gateway = llm_gateway or create_llm_gateway()
            if not isinstance(gateway, LLMGateway):
                raise TypeError("llm_gateway must be an LLMGateway instance")
            strategist = StrategyStrategist(StrategyPlanner(gateway))
        self._strategist = strategist
        super().__init__(
            metadata=SkillMetadata(
                id="strategy_skill",
                name="strategy_skill",
                description="Маркетинговый и бизнес-стратегический анализ (AST для Document Renderer)",
                capabilities=["strategy_analysis"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "goal": {"type": "string"},
                        "context": {"type": "object"},
                        "strategy_type": {"type": "string"},
                        "audience": {"type": "string"},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "strategy_result": {"type": "object"},
                        "document_ast": {"type": "object"},
                    },
                },
            ),
            capabilities=[
                Capability(
                    name="strategy_analysis",
                    description="Маркетинговая/бизнес-стратегия, SWOT, позиционирование и рекомендации",
                    category="strategy",
                    critical=False,
                ),
            ],
        )

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        goal = payload.get("goal") or payload.get("user_goal") or payload.get("description")
        if not goal:
            return {
                "status": "failed",
                "skill": self.name(),
                "message": "goal is required for strategy analysis",
                "payload_keys": list(payload.keys()),
            }

        context = dict(payload.get("context") or {})
        learning_rules = list(
            payload.get("learning_rules")
            or context.get("learning_rules")
            or context.get("learning_context")
            or []
        )
        type_raw = payload.get("strategy_type") or context.get("strategy_type")
        strategy_type = None
        if type_raw:
            try:
                strategy_type = StrategyType(str(type_raw).lower())
            except ValueError:
                strategy_type = None

        request = StrategyRequest(
            goal=str(goal),
            client_context=dict(
                payload.get("client_context")
                or context.get("client_context")
                or context.get("client")
                or {}
            ),
            project_context=dict(
                payload.get("project_context")
                or context.get("project_context")
                or context.get("project")
                or {}
            ),
            audience=payload.get("audience") or context.get("audience"),
            constraints=list(payload.get("constraints") or context.get("constraints") or []),
            strategy_type=strategy_type,
            learning_rules=learning_rules,
            brand_profile=payload.get("brand_profile") or context.get("brand_profile"),
            metadata=dict(payload.get("metadata") or {}),
        )

        result = await self._strategist.analyze(
            request,
            trace_id=str(payload.get("trace_id") or "-"),
        )
        memory_items = prepare_strategy_memory_items(
            result,
            client_id=payload.get("client_id"),
            project_id=payload.get("project_id"),
            session_id=payload.get("session_id"),
        )
        result.memory_candidates = [item.model_dump(mode="json") for item in memory_items]

        return {
            "status": "completed" if result.document_ast else "failed",
            "skill": self.name(),
            "strategy_result": result.model_dump(mode="json"),
            "document_ast": result.document_ast,
            "memory_candidates": result.memory_candidates,
            "analysis_warnings": result.analysis_warnings,
            "metadata": result.metadata,
            "message": result.summary if not result.document_ast else None,
        }
