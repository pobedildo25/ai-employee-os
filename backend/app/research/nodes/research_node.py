import logging
from typing import Any

from app.agent_runtime.state.models import AgentState
from app.research.manager import ResearchManager
from app.research.models import ResearchRequest, ResearchType

logger = logging.getLogger(__name__)

RESEARCH_NODE = "research"


class ResearchNode:
    """LangGraph-ready node — research then hand off to strategy/document skills."""

    name = RESEARCH_NODE

    def __init__(self, manager: ResearchManager) -> None:
        self._manager = manager

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        context = state.get("execution_context") or state.get("context") or {}
        metadata = state.get("metadata") or {}
        understanding = state.get("understanding") or {}
        query = (
            metadata.get("research_query")
            or context.get("research_query")
            or understanding.get("goal")
            or state.get("user_input")
            or ""
        )
        type_raw = metadata.get("research_type") or context.get("research_type") or "MARKET_RESEARCH"
        try:
            research_type = ResearchType(str(type_raw).upper())
        except ValueError:
            research_type = ResearchType.MARKET_RESEARCH

        request = ResearchRequest(
            query=str(query),
            research_type=research_type,
            client_id=context.get("client_id") or (context.get("client_context") or {}).get("id"),
            context=dict(context) if isinstance(context, dict) else {},
            constraints=list(context.get("constraints") or metadata.get("constraints") or []),
            learning_rules=list(context.get("learning_context") or context.get("learning_rules") or []),
        )
        result = await self._manager.run(request, trace_id=state.get("trace_id", "-"))
        research_dump = result.model_dump(mode="json")
        update = {
            "current_step": self.name,
            "status": "research_ready" if result.document_ast else "research_incomplete",
            "research_result": research_dump,
            "document_ast": result.document_ast,
            "document_creation_result": {
                "document_ast": result.document_ast,
                "metadata": {**result.metadata, "document_type": "docx", "kind": "research"},
                "missing_information": result.analysis_warnings,
            },
            "execution_context": {
                **(context if isinstance(context, dict) else {}),
                "research_context": research_dump,
            },
        }
        logger.info(
            "research node | execution_id=%s sources=%s",
            state.get("execution_id", "-"),
            len(result.sources),
        )
        return update
