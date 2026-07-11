import logging
from typing import Any
from uuid import UUID

from app.agent_runtime.state.models import AgentState
from app.task_queue.manager import TaskQueueManager
from app.workspace.manager import WorkspaceManager

logger = logging.getLogger(__name__)

BACKGROUND_TASK_NODE = "background_task"


class BackgroundTaskNode:
    """LangGraph-ready node for enqueueing background work — not wired into main workflow."""

    name = BACKGROUND_TASK_NODE

    def __init__(
        self,
        queue_manager: TaskQueueManager,
        workspace_manager: WorkspaceManager | None = None,
    ) -> None:
        self._queue = queue_manager
        self._workspace = workspace_manager

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        _log_node(state, self.name, "started")
        metadata = state.get("metadata") or {}
        context = state.get("context") or {}

        task_type = metadata.get("background_task_type") or context.get("background_task_type")
        if not task_type:
            update = {
                "current_step": self.name,
                "status": "background_task_skipped",
                "background_task": None,
            }
            _log_node({**state, **update}, self.name, "skipped")
            return update

        payload = metadata.get("background_task_payload") or context.get("background_task_payload") or {}
        priority = int(metadata.get("background_task_priority") or 100)
        task = await self._queue.enqueue(
            task_type=str(task_type),
            payload=dict(payload) if isinstance(payload, dict) else {},
            priority=priority,
            metadata={
                "execution_id": state.get("execution_id"),
                "trace_id": state.get("trace_id"),
            },
        )

        workspace_id = _to_uuid(
            metadata.get("workspace_id")
            or context.get("workspace_id")
            or (state.get("workspace_context") or {}).get("workspace_id")
        )
        if self._workspace is not None and workspace_id is not None:
            await self._workspace.track_background_task(workspace_id, task.id)

        update = {
            "current_step": self.name,
            "status": "background_task_enqueued",
            "background_task": task.model_dump(mode="json"),
        }
        _log_node({**state, **update}, self.name, "completed")
        return update


def _log_node(state: AgentState, node_name: str, status: str) -> None:
    logger.info(
        "graph node execution | execution_id=%s trace_id=%s node_name=%s status=%s",
        state.get("execution_id", "-"),
        state.get("trace_id", "-"),
        node_name,
        status,
    )


def _to_uuid(value: object | None) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except ValueError:
        return None
