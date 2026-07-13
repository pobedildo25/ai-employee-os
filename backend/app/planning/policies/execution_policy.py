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


def capabilities_require_llm_planner(capabilities: list[str] | None) -> bool:
    """LLM Planner is only justified for multi-capability dependent work."""
    return len(normalize_capabilities(capabilities)) >= 2


def plan_requires_orchestration(plan: TaskPlan | None) -> bool:
    """ExecutionGraph/Scheduler only for multi-step plans."""
    if plan is None:
        return False
    return len(plan.steps) > 1
