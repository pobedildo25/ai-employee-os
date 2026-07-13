"""Decision engine policies — route by structured DecisionType only.

No keyword matching and no inspection of raw user text.
"""

from enum import Enum

from app.agents.decision.models import DecisionType

CHAT_ACTIONS = frozenset(
    {
        DecisionType.RESPOND.value,
        DecisionType.ASK_CLARIFICATION.value,
    }
)
TASK_ACTIONS = frozenset(
    {
        DecisionType.EXECUTE.value,
        DecisionType.CREATE_PLAN.value,
    }
)


def normalize_action(action: str | DecisionType | None) -> str | None:
    """Normalize decision action to RESPOND|ASK_CLARIFICATION|EXECUTE|CREATE_PLAN."""
    if action is None:
        return None
    if isinstance(action, Enum):
        raw = action.value
    else:
        raw = action
    normalized = str(raw).strip().upper()
    # Guard against str(Enum) forms like "DecisionType.RESPOND".
    if "." in normalized:
        normalized = normalized.rsplit(".", 1)[-1]
    return normalized or None


def is_respond(action: str | None) -> bool:
    return normalize_action(action) == DecisionType.RESPOND.value


def is_clarification(action: str | None) -> bool:
    return normalize_action(action) == DecisionType.ASK_CLARIFICATION.value


def is_execute(action: str | None) -> bool:
    return normalize_action(action) == DecisionType.EXECUTE.value


def is_create_plan(action: str | None) -> bool:
    return normalize_action(action) == DecisionType.CREATE_PLAN.value


def is_chat_action(action: str | None) -> bool:
    return normalize_action(action) in CHAT_ACTIONS


def is_task_action(action: str | None) -> bool:
    return normalize_action(action) in TASK_ACTIONS


def should_invoke_planner(action: str | None) -> bool:
    """LLM TaskPlanner runs only for multi-stage CREATE_PLAN decisions."""
    return is_create_plan(action)


def should_direct_execute(action: str | None) -> bool:
    """Single-deliverable path: resolve skills and run without LLM planning."""
    return is_execute(action)


def requires_human_approval(action: str | None) -> bool:
    """Approval is reserved for multi-stage plans, not ordinary EXECUTE."""
    return is_create_plan(action)


def expects_capabilities(action: str | None) -> bool:
    return is_task_action(action)
