from typing import Any

from app.conversation.models import ConversationState, FlowMode


def format_progress_header() -> str:
    return "Думаю…"


def format_working_header(goal: str | None) -> str:
    """Task-aware working indicator so the user sees the bot understood the task."""
    text = (goal or "").strip()
    if not text:
        return "Принял, работаю над задачей…"
    if len(text) > 90:
        text = text[:87].rstrip() + "…"
    return f"Принял. Готовлю: {text}"


_FLOW_MODE_LABELS: dict[FlowMode, str] = {
    FlowMode.IDLE: "свободен",
    FlowMode.RUNNING: "выполняю задачу",
    FlowMode.WAITING_APPROVAL: "жду подтверждения плана",
    FlowMode.REVISION_PROMPTED: "жду правки",
    FlowMode.PENDING_CLARIFICATION: "жду уточнение",
    FlowMode.COMPLETED: "есть готовый результат",
    FlowMode.FAILED: "последняя задача не удалась",
    FlowMode.CANCELLED: "последняя задача отменена",
}


def format_slash_start() -> str:
    return (
        "Я NOVA — AI-сотрудник маркетингового агентства.\n\n"
        "Команды:\n"
        "/new — начать диалог заново\n"
        "/status — короткий статус\n"
        "/cancel — отменить текущую задачу\n\n"
        "Пока без живого web/research (включится отдельно). "
        "Могу готовить черновики документов и презентаций (docx/pptx)."
    )


def format_slash_new_confirm() -> str:
    return "Диалог сброшен. Можно начать заново."


def format_slash_nothing_to_cancel() -> str:
    return "Сейчас нечего отменять."


def format_slash_cancelled() -> str:
    return "Выполнение отменено."


def format_slash_status(convo: ConversationState) -> str:
    mode = _FLOW_MODE_LABELS.get(convo.flow_mode, str(convo.flow_mode.value))
    has_artifacts = "да" if convo.artifact_ids else "нет"
    last_id = convo.last_execution_id or "—"
    return (
        f"Сейчас: {mode}\n"
        f"Артефакты в диалоге: {has_artifacts}\n"
        f"Последний запрос: {last_id}"
    )




def format_progress(progress: dict[str, Any] | None, *, header: str | None = None) -> str:
    """Quiet ephemeral status — no checklist theater in chat history."""
    title = header or format_progress_header()
    if not progress:
        return title

    lines = progress.get("lines") or []
    active = next(
        (
            line
            for line in lines
            if str(line.get("status_label") or "").lower()
            in {"выполняется", "in_progress", "running"}
        ),
        None,
    )
    if active and active.get("title"):
        return f"{title}\n{active['title']}"
    return title


def format_approval_message(task_plan: dict[str, Any] | None) -> str:
    steps = (task_plan or {}).get("steps") or []
    if not steps:
        return "План готов. Начать выполнение?"

    lines = [
        f"{index}. {step.get('description') or step.get('capability')}"
        for index, step in enumerate(steps, start=1)
    ]
    return "План:\n\n" + "\n".join(lines) + "\n\nНачать выполнение?"


INCOMPLETE_COMPLETION_MESSAGE = (
    "Задача завершилась без результата. Можно уточнить запрос или попробовать ещё раз."
)

INCOMPLETE_REASON = "Нет артефакта и нет текста результата."


def format_completion_message(state: dict[str, Any]) -> str:
    reply = _extract_result_message(state)
    if reply:
        return reply
    return INCOMPLETE_COMPLETION_MESSAGE


def has_real_result_message(state: dict[str, Any]) -> bool:
    return _extract_result_message(state) is not None


def format_delivery_summary(artifacts: list[dict[str, Any]], state: dict[str, Any]) -> str:
    """Short confirmation after files — no quality score, no icon inventory."""
    _ = artifacts, state
    return "Готово."


def format_delivery_caption(artifacts: list[dict[str, Any]]) -> str | None:
    if not artifacts:
        return None
    count = len(artifacts)
    if count == 1:
        return "Готово."
    return f"Готово · {count} {_plural_files(count)}"


def _plural_files(count: int) -> str:
    mod10 = count % 10
    mod100 = count % 100
    if mod10 == 1 and mod100 != 11:
        return "файл"
    if 2 <= mod10 <= 4 and not (12 <= mod100 <= 14):
        return "файла"
    return "файлов"


def format_revision_prompt() -> str:
    return "Что изменить?"


def extract_creation_missing_information(state: dict[str, Any]) -> list[str]:
    """Missing-info items a document step reported when it could not draft anything."""
    result = state.get("document_creation_result")
    if not isinstance(result, dict):
        return []
    missing = result.get("missing_information") or []
    return [str(item) for item in missing if str(item).strip()]


def format_clarification_question(missing: list[str]) -> str:
    items = [item for item in missing if item and item.strip()]
    if not items:
        return "Уточните, пожалуйста, детали задачи — что именно подготовить?"
    listed = "; ".join(items)
    return f"Чтобы подготовить черновик, уточните: {listed}."


def format_error_message(reason: str | None = None) -> str:
    base = "Не удалось завершить задачу."
    if reason:
        return f"{base}\n\n{reason}"
    return base


def format_runtime_error_message(
    *,
    trace_id: str | None = None,
    execution_id: str | None = None,
    reason: str | None = None,
) -> str:
    # Ids stay in API/result payloads — not in the chat bubble.
    _ = trace_id, execution_id
    if reason:
        return f"Не удалось выполнить задачу.\n\n{reason}"
    return "Не удалось выполнить задачу. Можно попробовать ещё раз."


def extract_failure_reason(state: dict[str, Any]) -> str | None:
    task_execution = state.get("task_execution") or {}
    logs = task_execution.get("logs") or []
    for entry in reversed(logs):
        if entry.get("level") == "error" and entry.get("message"):
            return str(entry["message"])
    execution_state = state.get("execution_state") or {}
    if execution_state.get("failure_reason"):
        return str(execution_state["failure_reason"])
    if state.get("status") == "execution_failed":
        return "Ошибка при выполнении плана"
    return None


def extract_reply_text(state: dict[str, Any]) -> str:
    """Read reply fields from AgentState — does not generate text."""
    result = state.get("result")
    if isinstance(result, dict):
        for key in ("message", "response_message", "text"):
            value = result.get(key)
            if value:
                return str(value)

    decision = state.get("decision")
    if isinstance(decision, dict):
        for key in ("response_message", "clarification_question", "message"):
            value = decision.get(key)
            if value:
                return str(value)

    # Do NOT fall back to understanding.summary — that paraphrases the user
    # request and leaks into failed/waiting delivery paths as a fake answer.
    status = state.get("status")
    return str(status) if status else "ok"


def _extract_result_message(state: dict[str, Any]) -> str | None:
    result = state.get("result")
    if isinstance(result, dict):
        for key in ("message", "reply", "text", "summary"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    decision = state.get("decision") or {}
    for key in ("response_message", "clarification_question"):
        value = decision.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None
