import logging
from typing import Any

from app.agent_runtime.state.models import AgentState
from app.orchestration.execution_graph import build_execution_graph
from app.orchestration.models import ExecutionGraph
from app.orchestration.progress_tracker import ProgressTracker
from app.orchestration.state_manager import StateManager
from app.orchestration.store import get_execution_store_singleton
from app.orchestration.validators.execution_validator import ExecutionValidator
from app.planning.models import TaskPlan
from app.planning.policies.execution_policy import plan_requires_orchestration

logger = logging.getLogger(__name__)

ORCHESTRATION_NODE = "orchestration"


class OrchestrationNode:
    name = ORCHESTRATION_NODE

    def __init__(
        self,
        *,
        state_manager: StateManager | None = None,
        progress_tracker: ProgressTracker | None = None,
        validator: ExecutionValidator | None = None,
    ) -> None:
        self._state_manager = state_manager or StateManager()
        self._progress = progress_tracker or ProgressTracker()
        self._validator = validator or ExecutionValidator()
        self._store = get_execution_store_singleton()

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        _log_node(state, self.name, "started")
        plan_data = state.get("task_plan")

        if not plan_data:
            update = {
                "current_step": self.name,
                "status": "orchestration_skipped",
                "execution_graph": None,
                "execution_state": None,
                "progress": 0.0,
                "active_nodes": [],
                "completed_nodes": [],
                "failed_nodes": [],
            }
            _log_node({**state, **update}, self.name, "skipped")
            return update

        plan = TaskPlan.model_validate(plan_data)

        # Single-step plans skip ExecutionGraph / Scheduler / DependencyResolver.
        if not plan_requires_orchestration(plan):
            update = {
                "current_step": self.name,
                "status": "orchestration_skipped",
                "execution_graph": None,
                "execution_state": None,
                "progress": 0.0,
                "active_nodes": [],
                "completed_nodes": [],
                "failed_nodes": [],
                "telegram_progress": None,
            }
            _log_node({**state, **update}, self.name, "single_step_skip")
            return update

        graph = build_execution_graph(plan)
        self._validator.validate_graph(graph)

        execution_id = state.get("execution_id", "")
        execution_state = self._state_manager.create_state(execution_id, graph)
        execution_state.progress = self._progress.calculate_progress(graph)

        telegram_progress = self._progress.build_telegram_progress(
            execution_id,
            graph,
            progress=execution_state.progress,
        )

        from app.orchestration.models import ExecutionRecord

        self._store.save(
            ExecutionRecord(
                execution_id=execution_id,
                trace_id=state.get("trace_id", ""),
                graph=graph,
                state=execution_state,
                task_plan=plan.model_dump(mode="json"),
                telegram_progress=telegram_progress,
            )
        )

        update = _build_state_update(graph, execution_state, telegram_progress)
        update["current_step"] = self.name
        update["status"] = "orchestrated"
        _log_node({**state, **update}, self.name, "completed")
        return update


def _build_state_update(graph: ExecutionGraph, execution_state, telegram_progress) -> dict[str, Any]:
    return {
        "execution_graph": graph.model_dump(mode="json"),
        "execution_state": execution_state.model_dump(mode="json"),
        "progress": execution_state.progress,
        "active_nodes": list(execution_state.current_nodes),
        "completed_nodes": list(execution_state.completed_nodes),
        "failed_nodes": list(execution_state.failed_nodes),
        "telegram_progress": telegram_progress.model_dump(mode="json"),
    }


def _log_node(state: AgentState, node_name: str, status: str) -> None:
    logger.info(
        "graph node execution | execution_id=%s trace_id=%s node_name=%s status=%s",
        state.get("execution_id", "-"),
        state.get("trace_id", "-"),
        node_name,
        status,
    )
