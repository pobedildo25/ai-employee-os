from app.agents.decision.models import DecisionType

CHAT_DECISIONS = {
    DecisionType.RESPOND.value,
    DecisionType.ASK_CLARIFICATION.value,
}
TASK_DECISIONS = {
    DecisionType.CREATE_PLAN.value,
    DecisionType.EXECUTE.value,
}


def is_chat_decision(action: str | None) -> bool:
    return action in CHAT_DECISIONS


def is_task_decision(action: str | None) -> bool:
    return action in TASK_DECISIONS


def extract_chat_reply(decision: dict | None) -> str | None:
    if not decision:
        return None
    for key in ("response_message", "clarification_question"):
        value = decision.get(key)
        if value:
            return str(value)
    return None
