import logging
from typing import Any

from app.agent_runtime.state.models import AgentState
from app.observability.manager import ObservabilityManager
from app.observability.models import TraceStatus

logger = logging.getLogger(__name__)

OBSERVABILITY_NODE = "observability"


class ObservabilityNode:
    """LangGraph-ready observability node — not wired into main workflow."""

    name = OBSERVABILITY_NODE

    def __init__(self, manager: ObservabilityManager) -> None:
        self._manager = manager

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        trace_id = str(state.get("trace_id") or "-")
        execution_id = str(state.get("execution_id") or "-")
        status_raw = str(state.get("status") or "completed")
        action = (state.get("metadata") or {}).get("observability_action", "finish")

        if action == "start":
            trace = await self._manager.start_execution(
                trace_id=trace_id,
                execution_id=execution_id,
                metadata={"source": "observability_node"},
            )
            return {
                "current_step": self.name,
                "status": "observability_started",
                "observability_trace": trace.model_dump(mode="json"),
            }

        mapped = TraceStatus.FAILED if "fail" in status_raw.lower() else TraceStatus.COMPLETED
        try:
            existing = await self._manager.get_trace(trace_id)
            if existing is None:
                await self._manager.start_execution(
                    trace_id=trace_id,
                    execution_id=execution_id,
                    metadata={"source": "observability_node"},
                )
            trace = await self._manager.finish_execution(trace_id, status=mapped)
        except ValueError:
            logger.warning("observability node skipped missing trace | trace_id=%s", trace_id)
            return {
                "current_step": self.name,
                "status": "observability_skipped",
                "observability_trace": None,
            }

        return {
            "current_step": self.name,
            "status": "observability_recorded",
            "observability_trace": trace.model_dump(mode="json"),
        }
