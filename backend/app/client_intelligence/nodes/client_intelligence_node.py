import logging
from typing import Any

from app.agent_runtime.state.models import AgentState
from app.client_intelligence.manager import ClientIntelligenceManager

logger = logging.getLogger(__name__)

CLIENT_INTELLIGENCE_NODE = "client_intelligence"


class ClientIntelligenceNode:
    """LangGraph-ready node — builds ClientProfile without auto-persisting."""

    name = CLIENT_INTELLIGENCE_NODE

    def __init__(self, manager: ClientIntelligenceManager) -> None:
        self._manager = manager

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        context = state.get("execution_context") or state.get("context") or {}
        hints = state.get("context") or {}
        client_id = hints.get("client_id") or context.get("client_id") or (context.get("client_context") or {}).get("id")
        if not client_id:
            return {
                "current_step": self.name,
                "status": "client_intelligence_skipped",
                "client_intelligence_result": None,
            }

        result = await self._manager.build_profile(
            client_id,
            execution_context=dict(context) if isinstance(context, dict) else {},
            use_llm=bool((state.get("metadata") or {}).get("analyze_client_intelligence")),
            project_id=hints.get("project_id"),
            user_input=state.get("user_input", ""),
            trace_id=state.get("trace_id", "-"),
        )
        update = {
            "current_step": self.name,
            "status": "client_intelligence_ready",
            "client_intelligence_result": result.model_dump(mode="json"),
        }
        logger.info(
            "client intelligence node | execution_id=%s client_id=%s confidence=%s",
            state.get("execution_id", "-"),
            client_id,
            result.profile.confidence,
        )
        return update
