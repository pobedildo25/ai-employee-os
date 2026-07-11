from typing import Any


def format_progress_header() -> str:
    return "🧠 NOVA анализирует задачу"


def format_telegram_progress(progress: dict[str, Any] | None, *, header: str | None = None) -> str:
    title = header or format_progress_header()
    if not progress:
        return title

    lines = progress.get("lines") or []
    body_parts: list[str] = []
    for line in lines:
        name = line.get("title") or ""
        icon = line.get("status_icon") or "⌛"
        label = line.get("status_label") or "ожидает"
        body_parts.append(f"{icon} {name}")

    if not body_parts:
        return title
    return f"{title}\n\n" + "\n".join(body_parts)


def format_approval_message(task_plan: dict[str, Any] | None) -> str:
    steps = (task_plan or {}).get("steps") or []
    if not steps:
        return (
            "Я подготовил план выполнения.\n\n"
            "Начать выполнение?"
        )

    lines = [f"{index}. {step.get('description') or step.get('capability')}" for index, step in enumerate(steps, start=1)]
    plan_text = "\n".join(lines)
    return f"Я подготовил план:\n\n{plan_text}\n\nНачать выполнение?"


def format_completion_message(state: dict[str, Any]) -> str:
    quality = state.get("quality_check") or {}
    score = quality.get("score")
    score_line = f"\n\nQuality score: {score:.2f}" if isinstance(score, (int, float)) else ""
    return f"Готово.\n\nЕсли нужно что-то изменить — напишите.{score_line}"


def format_delivery_summary(artifacts: list[dict[str, Any]], state: dict[str, Any]) -> str:
    quality = state.get("quality_check") or {}
    score = quality.get("score")
    lines = ["✅ Готово", "", "Создано:"]
    for artifact in artifacts:
        name = artifact.get("name") or "файл"
        mime = (artifact.get("mime_type") or "").lower()
        icon = _artifact_icon(mime, name)
        lines.append(f"{icon} {name}")
    if isinstance(score, (int, float)):
        lines.extend(["", f"Quality score: {score:.2f}"])
    return "\n".join(lines)


def format_revision_prompt() -> str:
    return (
        "Что нужно изменить?\n\n"
        "Напишите, что исправить:\n"
        "• стиль\n"
        "• объём текста\n"
        "• структуру\n"
        "• содержание"
    )


def format_error_message(reason: str | None = None) -> str:
    base = "Не удалось завершить задачу."
    if reason:
        return f"{base}\n\nПричина: {reason}"
    return base


def format_runtime_error_message(
    *,
    trace_id: str | None = None,
    execution_id: str | None = None,
    reason: str | None = None,
) -> str:
    lines = ["Произошла ошибка при выполнении задачи. Я уже сохранил детали."]
    if trace_id:
        lines.append(f"trace_id: {trace_id}")
    if execution_id:
        lines.append(f"execution_id: {execution_id}")
    if reason:
        lines.append(f"Причина: {reason}")
    return "\n".join(lines)


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


def _artifact_icon(mime_type: str, name: str) -> str:
    lowered = name.lower()
    if "pptx" in lowered or "presentation" in mime_type:
        return "📊"
    if "pdf" in lowered or mime_type == "application/pdf":
        return "📕"
    if "png" in lowered or mime_type.startswith("image/"):
        return "🖼"
    return "📄"
