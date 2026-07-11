from typing import Any
from uuid import UUID

from app.context.models import ContextRequest
from app.context.providers.base import ContextProvider
from app.workspace.service import WorkspaceService


class WorkspaceContextProvider(ContextProvider):
    """Injects workspace state into ExecutionContext as workspace_context."""

    name = "workspace"

    def __init__(self, service: WorkspaceService) -> None:
        self._service = service

    async def fetch(self, request: ContextRequest) -> dict[str, Any]:
        workspace_id = _parse_uuid((request.metadata or {}).get("workspace_id"))
        snapshot: dict[str, Any] | None = None

        if workspace_id is not None:
            snapshot = await self._service.get_snapshot(workspace_id)
        elif request.client_id is not None:
            snapshot = await self._service.get_snapshot_for_client(request.client_id)

        if not snapshot:
            return {}
        return {"workspace_context": snapshot}


def _parse_uuid(value: object | None) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except ValueError:
        return None
