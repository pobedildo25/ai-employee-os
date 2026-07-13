from __future__ import annotations

from typing import Any

from app.agents.decision.policy import (
    requires_human_approval,
    should_direct_execute,
    should_invoke_planner,
)
from app.planning.models import PlanStep, StepStatus, TaskExecutionStatus, TaskPlan

MAX_STEP_RETRIES = 3

# Re-export decision-engine policies for planning/orchestration callers.
should_plan = should_invoke_planner


def requires_approval(decision_action: str | None, plan: TaskPlan | None = None) -> bool:
    """Human approval only for multi-step CREATE_PLAN work — not demoted single-step."""
    if not requires_human_approval(decision_action):
        return False
    if plan is None:
        return True
    return len(plan.steps) > 1


def should_retry_step(step: PlanStep, attempt: int) -> bool:
    if step.status != StepStatus.FAILED:
        return False
    return attempt < MAX_STEP_RETRIES


def map_execution_status_on_failure(retry_allowed: bool) -> TaskExecutionStatus:
    return TaskExecutionStatus.RUNNING if retry_allowed else TaskExecutionStatus.FAILED


def should_build_execution_plan(decision_action: str | None) -> bool:
    """True when a TaskPlan must exist (LLM plan or direct EXECUTE plan)."""
    return should_invoke_planner(decision_action) or should_direct_execute(decision_action)


def normalize_capabilities(capabilities: list[str] | None) -> list[str]:
    return [name.strip() for name in (capabilities or []) if name and str(name).strip()]


def plan_has_branching(plan: TaskPlan | None) -> bool:
    """True when a plan has multiple roots or non-linear dependency structure."""
    if plan is None or len(plan.steps) <= 1:
        return False
    step_ids = {step.id for step in plan.steps}
    roots = [
        step
        for step in plan.steps
        if not step.dependencies or not any(dep in step_ids for dep in step.dependencies)
    ]
    if len(roots) > 1:
        return True
    children: dict[Any, list[Any]] = {}
    for step in plan.steps:
        if len(step.dependencies) > 1:
            return True
        for dep in step.dependencies:
            children.setdefault(dep, []).append(step.id)
            if len(children[dep]) > 1:
                return True
    return False


def _meta_flag(sources: list[dict[str, Any] | None], *keys: str) -> bool:
    for source in sources:
        if not isinstance(source, dict):
            continue
        nested = source.get("metadata") if isinstance(source.get("metadata"), dict) else None
        for key in keys:
            if source.get(key) is True:
                return True
            if nested is not None and nested.get(key) is True:
                return True
    return False


def should_invoke_llm_planner(
    decision_action: str | None = None,
    capabilities: list[str] | None = None,
    *,
    decision: dict[str, Any] | None = None,
    understanding: Any | None = None,
    metadata: dict[str, Any] | None = None,
    plan: TaskPlan | None = None,
) -> bool:
    """LLM TaskPlanner runs only for CREATE_PLAN when structure is unknown or branching.

    Default for CREATE_PLAN with a known ordered capability list → direct sequenced plan
    (no LLM), even when there are multiple skills. Capability count alone is never enough.
    """
    action = decision_action
    if action is None and decision is not None:
        action = decision.get("action")
    if not should_invoke_planner(action):
        return False

    caps = normalize_capabilities(capabilities)
    understanding_data: dict[str, Any] | None = None
    if understanding is not None:
        if hasattr(understanding, "model_dump"):
            understanding_data = understanding.model_dump(mode="json")
        elif isinstance(understanding, dict):
            understanding_data = understanding
        if not caps and understanding_data is not None:
            caps = normalize_capabilities(list(understanding_data.get("required_capabilities") or []))

    # 0–1 capabilities: demote to direct/single — never LLM TaskPlanner.
    if len(caps) <= 1:
        return False

    if _meta_flag(
        [metadata, decision, understanding_data],
        "requires_llm_plan",
        "requires_multi_stage",
        "requires_planning",
    ):
        return True

    if plan_has_branching(plan):
        return True

    # Known ordered linear capability list → build_direct_execution_plan (no LLM).
    return False


# Backward-compatible name used by older tests/imports during Sprint C.
def capabilities_require_llm_planner(
    capabilities: list[str] | None,
    *,
    decision_action: str | None = "CREATE_PLAN",
    decision: dict[str, Any] | None = None,
    understanding: Any | None = None,
    metadata: dict[str, Any] | None = None,
    plan: TaskPlan | None = None,
) -> bool:
    """Deprecated alias — prefer should_invoke_llm_planner (count ≥ 2 is NOT enough)."""
    return should_invoke_llm_planner(
        decision_action,
        capabilities,
        decision=decision,
        understanding=understanding,
        metadata=metadata,
        plan=plan,
    )


def plan_requires_orchestration(plan: TaskPlan | None) -> bool:
    """ExecutionGraph/Scheduler only for multi-step plans."""
    if plan is None:
        return False
    return len(plan.steps) > 1
