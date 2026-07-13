import logging
from typing import Any

from app.agent_runtime.state.models import AgentState
from app.agents.decision.policy import should_direct_execute, should_invoke_planner
from app.agents.executive.models import AgentUnderstanding
from app.context.models import ExecutionContext
from app.planning.direct_plan import build_direct_execution_plan
from app.planning.planner import TaskPlanner
from app.planning.policies.execution_policy import (
    normalize_capabilities,
    should_invoke_llm_planner,
)
from app.skills.capability_resolver import (
    CapabilityResolutionError,
    resolve_capability_graph,
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
        metadata = state.get("metadata") or {}

        # Approval resume: reuse READY/APPROVED plan — skip re-planning / Executive re-analysis.
        resume_plan = metadata.get("resume_task_plan")
        if metadata.get("auto_approve") and isinstance(resume_plan, dict) and resume_plan.get("steps"):
            status_value = str(resume_plan.get("status") or "").upper()
            if status_value in {"READY", "APPROVED", "DRAFT"} or not status_value:
                steps = resume_plan.get("steps") or []
                update = {
                    "current_step": self.name,
                    "task_plan": resume_plan,
                    "status": "planned" if len(steps) > 1 else "direct_plan_ready",
                }
                _log_node({**state, **update}, self.name, "resumed_plan")
                return update

        try:
            capabilities = resolve_capability_graph(decision, understanding, self._registry)
        except CapabilityResolutionError as exc:
            update = {
                "current_step": self.name,
                "status": "planning_failed",
                "task_plan": None,
                "error": str(exc),
            }
            _log_node({**state, **update}, self.name, "failed")
            return update

        # Keep understanding hint aligned with Resolver-owned ordered list.
        understanding = understanding.model_copy(update={"required_capabilities": capabilities})

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

        # CREATE_PLAN demotion / direct path: LLM only when branching / explicit flag.
        # Single capability OR linear known ordered caps → direct sequenced plan (no LLM).
        if not should_invoke_llm_planner(
            action,
            capabilities,
            decision=decision,
            understanding=understanding,
            metadata=metadata,
        ):
            reason = (
                "demoted_single_capability"
                if len(normalize_capabilities(capabilities)) <= 1
                else "direct_linear_create_plan"
            )
            return self._direct_plan_update(state, understanding, capabilities, reason=reason)

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
