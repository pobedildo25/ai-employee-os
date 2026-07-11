import logging
from typing import Any

from app.agent_runtime.state.models import AgentState
from app.strategy.models import StrategyRequest, StrategyType
from app.strategy.strategist import StrategyStrategist

logger = logging.getLogger(__name__)

STRATEGY_NODE = "strategy"


class StrategyNode:
    """LangGraph-ready node — prepare strategy + AST before Document Creation/Render."""

    name = STRATEGY_NODE

    def __init__(self, strategist: StrategyStrategist) -> None:
        self._strategist = strategist

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        context = state.get("execution_context") or state.get("context") or {}
        metadata = state.get("metadata") or {}
        understanding = state.get("understanding") or {}
        goal = understanding.get("goal") or state.get("user_input") or ""
        learning = context.get("learning_context") or context.get("learning_rules") or []

        type_raw = metadata.get("strategy_type") or context.get("strategy_type")
        strategy_type = None
        if type_raw:
            try:
                strategy_type = StrategyType(str(type_raw).lower())
            except ValueError:
                strategy_type = None

        request = StrategyRequest(
            goal=str(goal),
            client_context=dict(context.get("client_context") or context.get("client") or {}),
            project_context=dict(context.get("project_context") or context.get("project") or {}),
            audience=metadata.get("audience") or context.get("audience"),
            constraints=list(context.get("constraints") or []),
            strategy_type=strategy_type,
            learning_rules=list(learning) if isinstance(learning, list) else [],
            brand_profile=context.get("brand_profile") or metadata.get("brand_profile"),
            metadata=dict(metadata),
        )
        result = await self._strategist.analyze(request, trace_id=state.get("trace_id", "-"))

        update: dict[str, Any] = {
            "current_step": self.name,
            "status": "strategy_ready" if result.document_ast else "strategy_incomplete",
            "strategy_result": result.model_dump(mode="json"),
            "document_ast": result.document_ast,
            "document_creation_result": {
                "document_ast": result.document_ast,
                "metadata": {
                    **result.metadata,
                    "document_type": result.metadata.get("document_type", "docx"),
                    "brand_profile": result.metadata.get("brand_profile"),
                },
                "missing_information": result.missing_information,
            },
        }
        logger.info(
            "strategy node | execution_id=%s type=%s insights=%s",
            state.get("execution_id", "-"),
            result.strategy_type.value,
            len(result.insights),
        )
        return update
