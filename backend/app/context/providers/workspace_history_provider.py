from typing import Any
from uuid import UUID

from app.context.models import ContextRequest
from app.context.providers.history_provider import (
    DEFAULT_HISTORY_MAX_MESSAGES,
    HistoryProvider,
    truncate_conversation_history,
)
from app.workspace.service import WorkspaceService


class WorkspaceHistoryProvider(HistoryProvider):
    """Reads dialogue buffer from Workspace conversation (durable across updates)."""

    name = "history"

    def __init__(
        self,
        workspace_service: WorkspaceService,
        max_messages: int = DEFAULT_HISTORY_MAX_MESSAGES,
    ) -> None:
        self._service = workspace_service
        self._max_messages = max_messages

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
        return {
            "conversation_history": truncate_conversation_history(
                list(conversation.messages),
                self._max_messages,
            )
        }
