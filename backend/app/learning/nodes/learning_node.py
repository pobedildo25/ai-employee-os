import logging
from typing import Any
from uuid import UUID

from app.agent_runtime.state.models import AgentState
from app.learning.manager import LearningManager
from app.learning.models import LearningSource

logger = logging.getLogger(__name__)

LEARNING_NODE = "learning"


class LearningNode:
    """LangGraph-ready learning node — optional; not required in main workflow."""

    name = LEARNING_NODE

    def __init__(self, manager: LearningManager) -> None:
        self._manager = manager

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        metadata = state.get("metadata") or {}
        context = state.get("context") or {}
        execution_context = state.get("execution_context") or {}
        feedback = (
            metadata.get("user_feedback")
            or metadata.get("learning_feedback")
            or context.get("user_feedback")
        )
        if not feedback:
            return {
                "current_step": self.name,
                "status": "learning_skipped",
                "learning_result": None,
            }

        client_id = _to_uuid(
            metadata.get("client_id") or context.get("client_id") or execution_context.get("client_id")
        )
        project_id = _to_uuid(
            metadata.get("project_id")
            or context.get("project_id")
            or execution_context.get("project_id")
        )
        source_raw = metadata.get("learning_source") or LearningSource.USER_FEEDBACK.value
        try:
            source = LearningSource(source_raw)
        except ValueError:
            source = LearningSource.USER_FEEDBACK

        rule = await self._manager.learn(
            str(feedback),
            source=source,
            client_id=client_id,
            project_id=project_id,
            context=execution_context,
            trace_id=state.get("trace_id", "-"),
            force=bool(metadata.get("force_learn", False)),
        )
        return {
            "current_step": self.name,
            "status": "learning_completed" if rule else "learning_noop",
            "learning_result": rule.model_dump(mode="json") if rule else None,
        }


def _to_uuid(value: object | None) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except ValueError:
        return None
