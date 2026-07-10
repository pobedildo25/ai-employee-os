from app.agents.decision.models import DecisionType


def should_create_document(decision_action: str | None) -> bool:
    return decision_action in {
        DecisionType.CREATE_PLAN.value,
        DecisionType.EXECUTE.value,
    }


def should_render_document(
    *,
    decision_action: str | None,
    missing_information: list[str] | None,
    has_document_ast: bool,
) -> bool:
    if not has_document_ast:
        return False
    if missing_information:
        return False
    return decision_action in {
        DecisionType.CREATE_PLAN.value,
        DecisionType.EXECUTE.value,
    }
