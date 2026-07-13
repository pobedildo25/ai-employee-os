import logging
from typing import Any

from app.agent_runtime.state.models import AgentState
from app.agents.decision.policy import should_direct_execute, should_invoke_planner
from app.agents.executive.models import AgentUnderstanding
from app.context.models import ExecutionContext
from app.planning.direct_plan import build_direct_execution_plan
from app.planning.planner import TaskPlanner
from app.planning.policies.execution_policy import (
    capabilities_require_llm_planner,
    normalize_capabilities,
)
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
        understanding = AgentUnderstanding.model_validate(state.get("understanding") or {})
        capabilities = normalize_capabilities(list(understanding.required_capabilities))

        # EXECUTE → direct plan, never LLM Planner.
        if should_direct_execute(action):
            return self._direct_plan_update(state, understanding, capabilities, reason="direct_execute")

        if not should_invoke_planner(action):
            update = {
                "current_step": self.name,
                "status": "planning_skipped",
                "task_plan": None,
            }
            _log_node({**state, **update}, self.name, "skipped")
            return update

        # CREATE_PLAN with 0–1 capabilities is not multi-stage — demote to direct plan.
        if not capabilities_require_llm_planner(capabilities):
            return self._direct_plan_update(
                state,
                understanding,
                capabilities,
                reason="demoted_single_capability",
            )

        execution_context = ExecutionContext.model_validate(
            state.get("execution_context") or {"user_input": state.get("user_input", "")}
        )
        available = self._registry.list_available()

        plan = await self._planner.create_plan(
            understanding=understanding,
            execution_context=execution_context,
            available_capabilities=available,
            trace_id=state.get("trace_id", "-"),
        )

        # If LLM still produced a single step, treat as direct (no multi-stage graph needed).
        if len(plan.steps) <= 1:
            logger.info(
                "planner demoted multi-stage result to single-step | trace_id=%s steps=%d",
                state.get("trace_id", "-"),
                len(plan.steps),
            )

        update = {
            "current_step": self.name,
            "task_plan": plan.model_dump(mode="json"),
            "status": "planned" if len(plan.steps) > 1 else "direct_plan_ready",
        }
        _log_node({**state, **update}, self.name, "completed")
        return update

    def _direct_plan_update(
        self,
        state: AgentState,
        understanding: AgentUnderstanding,
        capabilities: list[str],
        *,
        reason: str,
    ) -> dict[str, Any]:
        plan = build_direct_execution_plan(
            goal=understanding.goal,
            summary=understanding.summary,
            required_capabilities=capabilities,
        )
        update = {
            "current_step": self.name,
            "task_plan": plan.model_dump(mode="json"),
            "status": "direct_plan_ready",
        }
        _log_node({**state, **update}, self.name, reason)
        return update


def _log_node(state: AgentState, node_name: str, status: str) -> None:
    logger.info(
        "graph node execution | execution_id=%s trace_id=%s node_name=%s status=%s",
        state.get("execution_id", "-"),
        state.get("trace_id", "-"),
        node_name,
        status,
    )
