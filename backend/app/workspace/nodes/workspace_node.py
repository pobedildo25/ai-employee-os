import logging
from typing import Any
from uuid import UUID

from app.agent_runtime.state.models import AgentState
from app.workspace.service import WorkspaceService

logger = logging.getLogger(__name__)

WORKSPACE_NODE = "workspace"


class WorkspaceNode:
    """LangGraph-ready node for workspace open — not wired into main workflow yet."""

    name = WORKSPACE_NODE

    def __init__(self, service: WorkspaceService) -> None:
        self._service = service

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        _log_node(state, self.name, "started")
        context = state.get("context") or {}
        execution_context = state.get("execution_context") or {}
        metadata = state.get("metadata") or {}

        client_id = _to_uuid(
            metadata.get("client_id")
            or context.get("client_id")
            or execution_context.get("client_id")
        )
        if client_id is None:
            update = {
                "current_step": self.name,
                "status": "workspace_skipped",
                "workspace_context": None,
            }
            _log_node({**state, **update}, self.name, "skipped")
            return update

        snapshot = await self._service.open(
            client_id=client_id,
            project_id=_to_uuid(
                metadata.get("project_id")
                or context.get("project_id")
                or execution_context.get("project_id")
            ),
            task_id=_to_uuid(metadata.get("task_id") or context.get("task_id")),
            artifact_id=_to_uuid(metadata.get("artifact_id") or context.get("artifact_id")),
            metadata={"source": "workspace_node", "execution_id": state.get("execution_id")},
            open_session=bool(metadata.get("open_session", True)),
        )

        update = {
            "current_step": self.name,
            "status": "workspace_ready",
            "workspace_context": snapshot,
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
