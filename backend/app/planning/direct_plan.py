"""Build a direct TaskPlan for EXECUTE without invoking the LLM Planner."""

from app.planning.models import PlanStatus, PlanStep, TaskPlan


_CAPABILITY_LABELS_RU = {
    "document_generation": "Подготовка документа",
    "document_analysis": "Анализ документа",
    "document_rendering": "Рендер документа",
    "document_revision": "Правка документа",
    "presentation_design": "Подготовка презентации",
    "strategy_analysis": "Стратегический анализ",
    "research": "Исследование",
    "data_analysis": "Анализ данных",
    "brand_style": "Фирменный стиль",
}


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
        label = _CAPABILITY_LABELS_RU.get(capability, capability)
        step = PlanStep(
            description=label,
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
