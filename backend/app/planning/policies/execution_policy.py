from app.agents.decision.models import DecisionType
from app.planning.models import PlanStep, StepStatus, TaskExecutionStatus

MAX_STEP_RETRIES = 3


def should_retry_step(step: PlanStep, attempt: int) -> bool:
    if step.status != StepStatus.FAILED:
        return False
    return attempt < MAX_STEP_RETRIES


def requires_approval(decision_action: str | None) -> bool:
    return decision_action in {
        DecisionType.CREATE_PLAN.value,
        DecisionType.EXECUTE.value,
    }


def should_plan(decision_action: str | None) -> bool:
    return decision_action in {
        DecisionType.CREATE_PLAN.value,
        DecisionType.EXECUTE.value,
    }


def map_execution_status_on_failure(retry_allowed: bool) -> TaskExecutionStatus:
    return TaskExecutionStatus.RUNNING if retry_allowed else TaskExecutionStatus.FAILED
