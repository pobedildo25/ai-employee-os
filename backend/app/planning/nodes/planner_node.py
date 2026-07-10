import logging
from typing import Any

from app.agent_runtime.state.models import AgentState
from app.agents.executive.models import AgentUnderstanding
from app.context.models import ExecutionContext
from app.planning.planner import TaskPlanner
from app.planning.policies.execution_policy import should_plan
from app.skills.registry import CapabilityRegistry

logger = logging.getLogger(__name__)

PLANNER_NODE = "planner"


class PlannerNode:
    name = PLANNER_NODE

    def __init__(self, planner: TaskPlanner, registry: CapabilityRegistry) -> None:
        self._planner = planner
        self._registry = registry

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        _log_node(state, self.name, "started")
        decision = state.get("decision") or {}
        action = decision.get("action")

        if not should_plan(action):
            update = {
                "current_step": self.name,
                "status": "planning_skipped",
                "task_plan": None,
            }
            _log_node({**state, **update}, self.name, "skipped")
            return update

        understanding = AgentUnderstanding.model_validate(state.get("understanding") or {})
        execution_context = ExecutionContext.model_validate(
            state.get("execution_context") or {"user_input": state.get("user_input", "")}
        )
        capabilities = self._registry.list_available()

        plan = await self._planner.create_plan(
            understanding=understanding,
            execution_context=execution_context,
            available_capabilities=capabilities,
            trace_id=state.get("trace_id", "-"),
        )

        update = {
            "current_step": self.name,
            "task_plan": plan.model_dump(mode="json"),
            "status": "planned",
        }
        _log_node({**state, **update}, self.name, "completed")
        return update


def _log_node(state: AgentState, node_name: str, status: str) -> None:
    logger.info(
        "graph node execution | execution_id=%s trace_id=%s node_name=%s status=%s",
        state.get("execution_id", "-"),
        state.get("trace_id", "-"),
        node_name,
        status,
    )
