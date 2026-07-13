from app.adapters.telegram.conversation_store import PendingClarification


def merge_clarification_answer(pending: PendingClarification, user_answer: str) -> str:
    """Combine the original task goal with the user's clarification answer."""
    goal = (pending.original_goal or pending.original_user_input or "").strip()
    answer = user_answer.strip()
    if not answer:
        return goal

    parts = [goal] if goal else []
    if pending.missing_information:
        missing = "; ".join(item for item in pending.missing_information if item)
        if missing:
            parts.append(f"Нужно уточнить: {missing}")
    parts.append(f"Ответ пользователя: {answer}")
    return ". ".join(parts)


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
        understanding=understanding.model_dump(mode="json"),
    )
