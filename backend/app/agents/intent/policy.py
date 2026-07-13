from app.agents.decision.models import DecisionType
from app.agents.decision.policy import (
    is_chat_action,
    is_task_action,
    should_direct_execute,
    should_invoke_planner,
)

CHAT_DECISIONS = {
    DecisionType.RESPOND.value,
    DecisionType.ASK_CLARIFICATION.value,
}
TASK_DECISIONS = {
    DecisionType.CREATE_PLAN.value,
    DecisionType.EXECUTE.value,
}


def is_chat_decision(action: str | None) -> bool:
    return is_chat_action(action)


def is_task_decision(action: str | None) -> bool:
    return is_task_action(action)


def needs_planner(action: str | None) -> bool:
    return should_invoke_planner(action)


def needs_direct_execution(action: str | None) -> bool:
    return should_direct_execute(action)


def extract_chat_reply(decision: dict | None) -> str | None:
    if not decision:
        return None
    for key in ("response_message", "clarification_question"):
        value = decision.get(key)
        if value:
            return str(value)
    return None
