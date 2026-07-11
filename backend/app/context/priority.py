from typing import Any

from app.context.models import ExecutionContext

# Primary context ordering — higher items take precedence when merging or presenting.
CONTEXT_PRIORITY: tuple[str, ...] = (
    "user_input",
    "current_task",
    "project_context",
    "client_context",
    "artifact_context",
    "knowledge_context",
    "research_context",
    "client_intelligence_context",
    "learning_context",
    "preferences",
    "conversation_history",
)


def build_prioritized_context(context: ExecutionContext) -> dict[str, Any]:
    """Return context fields ordered by priority for downstream agents."""
    raw: dict[str, Any] = {
        "user_input": context.user_input,
        "current_task": context.current_task,
        "project_context": context.project_context,
        "client_context": context.client_context,
        "artifact_context": context.artifact_context,
        "knowledge_context": context.knowledge_context,
        "research_context": context.research_context,
        "client_intelligence_context": context.client_intelligence_context,
        "learning_context": context.learning_context,
        "preferences": context.preferences,
        "conversation_history": context.conversation_history,
        "metadata": context.metadata,
    }
    if context.extensions:
        raw["extensions"] = context.extensions
    if context.memory_context:
        raw["memory_context"] = context.memory_context
    if context.workspace_context:
        raw["workspace_context"] = context.workspace_context

    prioritized = {key: raw[key] for key in CONTEXT_PRIORITY if _has_value(raw.get(key))}
    if context.memory_context:
        prioritized["memory_context"] = raw["memory_context"]
    if context.workspace_context:
        prioritized["workspace_context"] = raw["workspace_context"]
    return prioritized


def sort_context_keys(keys: list[str]) -> list[str]:
    """Sort arbitrary context keys according to the priority order."""
    priority_index = {name: index for index, name in enumerate(CONTEXT_PRIORITY)}
    return sorted(keys, key=lambda key: priority_index.get(key, len(CONTEXT_PRIORITY)))


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, dict)) and not value:
        return False
    return True
