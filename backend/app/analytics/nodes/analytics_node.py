import logging
from typing import Any

from app.agent_runtime.state.models import AgentState
from app.analytics.manager import AnalyticsManager
from app.analytics.models import AnalyticsRequest, AnalyticsType

logger = logging.getLogger(__name__)

ANALYTICS_NODE = "analytics"


class AnalyticsNode:
    """LangGraph-ready node — analytics report AST for Document/Presentation chains."""

    name = ANALYTICS_NODE

    def __init__(self, manager: AnalyticsManager) -> None:
        self._manager = manager

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        context = state.get("execution_context") or state.get("context") or {}
        metadata = state.get("metadata") or {}
        type_raw = metadata.get("analytics_type") or context.get("analytics_type") or "CLIENT_PERFORMANCE"
        try:
            analytics_type = AnalyticsType(str(type_raw).upper())
        except ValueError:
            analytics_type = AnalyticsType.CLIENT_PERFORMANCE

        request = AnalyticsRequest(
            analytics_type=analytics_type,
            client_id=context.get("client_id") or (context.get("client_context") or {}).get("id"),
            project_id=context.get("project_id") or (context.get("project_context") or {}).get("id"),
            context=dict(context) if isinstance(context, dict) else {},
            learning_rules=list(context.get("learning_context") or context.get("learning_rules") or []),
            goal=(state.get("understanding") or {}).get("goal") or state.get("user_input"),
        )
        result = await self._manager.run(request, trace_id=state.get("trace_id", "-"))
        update = {
            "current_step": self.name,
            "status": "analytics_ready" if result.document_ast else "analytics_incomplete",
            "analytics_result": result.model_dump(mode="json"),
            "document_ast": result.document_ast,
            "document_creation_result": {
                "document_ast": result.document_ast,
                "metadata": {**result.metadata, "document_type": "docx", "kind": "analytics"},
                "missing_information": result.analysis_warnings,
            },
        }
        logger.info(
            "analytics node | execution_id=%s type=%s insights=%s",
            state.get("execution_id", "-"),
            result.analytics_type.value,
            len(result.insights),
        )
        return update
