"""Build a direct TaskPlan for EXECUTE without invoking the LLM Planner."""

from app.ux.human_labels import humanize_direct_plan_label
from app.planning.models import PlanStatus, PlanStep, TaskPlan


def build_direct_execution_plan(
    *,
    goal: str,
    summary: str,
    required_capabilities: list[str],
) -> TaskPlan:
    """One ready step per capability, sequenced in listed order (no LLM planning)."""
    capabilities = [name.strip() for name in required_capabilities if name and str(name).strip()]
    steps: list[PlanStep] = []
    previous_id = None
    for capability in capabilities:
        step = PlanStep(
            description=humanize_direct_plan_label(capability),
            capability=capability,
            dependencies=[previous_id] if previous_id is not None else [],
        )
        steps.append(step)
        previous_id = step.id
    return TaskPlan(
        goal=goal or "Выполнение запроса",
        summary=summary or goal or "Прямое выполнение",
        steps=steps,
        required_capabilities=capabilities,
        status=PlanStatus.READY,
    )
