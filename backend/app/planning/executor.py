import logging
from datetime import datetime
from uuid import UUID

from app.planning.interfaces.executor import TaskExecutorInterface
from app.planning.models import (
    ExecutionLogEntry,
    PlanStatus,
    PlanStep,
    StepStatus,
    TaskExecution,
    TaskExecutionStatus,
    TaskPlan,
)
from app.planning.policies.execution_policy import (
    MAX_STEP_RETRIES,
    is_critical_capability,
    is_retryable_failure,
    should_retry_step,
)
from app.skills.registry import CapabilityRegistry

logger = logging.getLogger(__name__)


class TaskExecutorError(Exception):
    """Raised when task execution fails irrecoverably."""


class TaskExecutor(TaskExecutorInterface):
    async def execute(
        self,
        plan: TaskPlan,
        registry: CapabilityRegistry,
        *,
        task_id: UUID | None = None,
        trace_id: str = "-",
        execution_context: dict | None = None,
    ) -> TaskExecution:
        execution = TaskExecution(
            task_id=task_id or plan.id,
            plan_id=plan.id,
            status=TaskExecutionStatus.RUNNING,
            logs=[
                ExecutionLogEntry(message=f"Execution started for plan {plan.id}"),
            ],
        )
        context = dict(execution_context or {})

        ordered_steps = _order_steps(plan.steps)
        plan.status = PlanStatus.READY
        completed_ids: set[UUID] = set()

        for step in ordered_steps:
            if not all(dep in completed_ids for dep in step.dependencies):
                step.status = StepStatus.SKIPPED
                execution.logs.append(
                    ExecutionLogEntry(
                        step_id=step.id,
                        level="warning",
                        message=f"Step skipped — unmet dependencies: {step.description}",
                    )
                )
                continue

            execution.current_step = step.id
            step.status = StepStatus.RUNNING
            execution.logs.append(
                ExecutionLogEntry(step_id=step.id, message=f"Step started: {step.description}")
            )

            success = await self._run_step_with_retry(step, registry, execution, trace_id, context)
            if not success:
                plan.status = PlanStatus.FAILED
                execution.status = TaskExecutionStatus.FAILED
                execution.logs.append(
                    ExecutionLogEntry(
                        step_id=step.id,
                        level="error",
                        message=f"Execution failed at step: {step.description}",
                    )
                )
                return execution

            completed_ids.add(step.id)

        plan.status = PlanStatus.COMPLETED
        execution.status = TaskExecutionStatus.COMPLETED
        execution.current_step = None
        execution.results = {
            "goal": plan.goal,
            "summary": plan.summary,
            "steps_completed": len([s for s in plan.steps if s.status == StepStatus.COMPLETED]),
        }
        execution.logs.append(ExecutionLogEntry(message="Execution completed successfully"))
        logger.info("task execution completed | trace_id=%s plan_id=%s", trace_id, plan.id)
        return execution

    async def _run_step_with_retry(
        self,
        step: PlanStep,
        registry: CapabilityRegistry,
        execution: TaskExecution,
        trace_id: str,
        execution_context: dict,
    ) -> bool:
        for attempt in range(1, MAX_STEP_RETRIES + 1):
            try:
                result = await self._execute_step(step, registry, execution_context)
                if not _skill_result_succeeded(result):
                    status = result.get("status") if isinstance(result, dict) else None
                    step.status = StepStatus.FAILED
                    step.result = result
                    execution.logs.append(
                        ExecutionLogEntry(
                            step_id=step.id,
                            level="error",
                            message=(
                                f"Step failed (attempt {attempt}): "
                                f"skill returned status={status!r}"
                            ),
                        )
                    )
                    logger.warning(
                        "step skill incomplete | trace_id=%s step_id=%s attempt=%d status=%s",
                        trace_id,
                        step.id,
                        attempt,
                        status,
                    )
                    if not is_retryable_failure(status) or not should_retry_step(step, attempt):
                        if _giveup_is_tolerable(step, execution, registry):
                            return True
                        return False
                    step.status = StepStatus.PENDING
                    continue
                step.status = StepStatus.COMPLETED
                step.result = result
                execution.logs.append(
                    ExecutionLogEntry(
                        step_id=step.id,
                        message=f"Step completed: {step.description}",
                    )
                )
                return True
            except Exception as exc:
                step.status = StepStatus.FAILED
                execution.logs.append(
                    ExecutionLogEntry(
                        step_id=step.id,
                        level="error",
                        message=f"Step failed (attempt {attempt}): {exc}",
                    )
                )
                logger.warning(
                    "step execution failed | trace_id=%s step_id=%s attempt=%d error=%s",
                    trace_id,
                    step.id,
                    attempt,
                    exc,
                )
                if not should_retry_step(step, attempt):
                    if _giveup_is_tolerable(step, execution, registry):
                        return True
                    return False
                step.status = StepStatus.PENDING

        return False

    async def _execute_step(
        self,
        step: PlanStep,
        registry: CapabilityRegistry,
        execution_context: dict,
    ) -> dict:
        skill = registry.get_skill_for_capability(step.capability)
        if skill is None:
            raise TaskExecutorError(f"No skill registered for capability: {step.capability}")

        payload = {
            "step_id": str(step.id),
            "description": step.description,
            "capability": step.capability,
            "goal": execution_context.get("user_goal") or execution_context.get("user_input"),
            "user_goal": execution_context.get("user_goal") or execution_context.get("user_input"),
            "context": execution_context,
            **execution_context,
        }
        return await skill.execute(payload)


def _giveup_is_tolerable(
    step: PlanStep,
    execution: TaskExecution,
    registry: CapabilityRegistry | None = None,
) -> bool:
    """Non-critical enrichment steps degrade to skipped instead of failing the task."""
    if is_critical_capability(step.capability, registry):
        return False
    reason = "enrichment unavailable"
    if isinstance(step.result, dict):
        reason = str(step.result.get("message") or step.result.get("status") or reason)
    step.status = StepStatus.COMPLETED
    step.result = {"status": "skipped", "skill": step.capability, "reason": reason}
    execution.logs.append(
        ExecutionLogEntry(
            step_id=step.id,
            message=f"Enrichment step skipped (best-effort): {step.capability} — {reason}",
        )
    )
    logger.warning(
        "step enrichment skipped | step_id=%s capability=%s reason=%s",
        step.id,
        step.capability,
        reason,
    )
    return True


_SUCCESS_SKILL_STATUSES = frozenset({"completed", "success", "ok"})


def _skill_result_succeeded(result: object) -> bool:
    """Only an explicit success status counts; non-dict / missing status → failure."""
    if not isinstance(result, dict):
        return False
    status = result.get("status")
    if status is None:
        return False
    return str(status).strip().lower() in _SUCCESS_SKILL_STATUSES


def _order_steps(steps: list[PlanStep]) -> list[PlanStep]:
    ordered: list[PlanStep] = []
    remaining = list(steps)
    while remaining:
        progress = False
        for step in list(remaining):
            if all(dep in {item.id for item in ordered} for dep in step.dependencies):
                ordered.append(step)
                remaining.remove(step)
                progress = True
        if not progress:
            ordered.extend(remaining)
            break
    return ordered
