from typing import Any
from uuid import UUID

from app.context.models import ContextRequest
from app.context.providers.history_provider import HistoryProvider
from app.workspace.service import WorkspaceService


class WorkspaceHistoryProvider(HistoryProvider):
    """Reads dialogue buffer from Workspace conversation (durable across updates)."""

    name = "history"

    def __init__(self, workspace_service: WorkspaceService) -> None:
        self._service = workspace_service

    async def fetch(self, request: ContextRequest) -> dict[str, Any]:
        if not request.session_id:
            return {"conversation_history": []}
        try:
            session_id = UUID(str(request.session_id))
        except (TypeError, ValueError):
            return {"conversation_history": []}

        conversation = await self._service.manager.get_conversation_by_session(session_id)
        if conversation is None:
            return {"conversation_history": []}
        return {"conversation_history": list(conversation.messages)}
