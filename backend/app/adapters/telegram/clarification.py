from app.adapters.telegram.conversation_store import PendingClarification


def merge_clarification_answer(pending: PendingClarification, user_answer: str) -> str:
    """Combine the original task goal with the user's clarification answer."""
    goal = pending.original_goal or pending.original_user_input
    answer = user_answer.strip()
    if not answer:
        return goal
    return f"{goal}. Уточнение: {answer}"


def build_pending_clarification(
    *,
    user_input: str,
    classification,
) -> PendingClarification:
    understanding = classification.understanding
    decision = classification.decision
    return PendingClarification(
        original_goal=understanding.goal or user_input,
        original_user_input=user_input,
        intent=decision.action.value,
        missing_information=list(understanding.missing_information or []),
        understanding=understanding.model_dump(),
    )
