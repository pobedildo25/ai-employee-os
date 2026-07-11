from typing import Any

from app.context.models import ContextRequest
from app.context.providers.base import ContextProvider
from app.knowledge.manager import KnowledgeManager


class KnowledgeContextProvider(ContextProvider):
    """Injects Client Knowledge Base into ExecutionContext as knowledge_context."""

    name = "knowledge"

    def __init__(self, manager: KnowledgeManager) -> None:
        self._manager = manager

    async def fetch(self, request: ContextRequest) -> dict[str, Any]:
        if request.client_id is None:
            return {}

        items = await self._manager.get_context_for_client(
            request.client_id,
            query=request.user_input,
            limit=10,
        )
        if not items:
            return {}
        return {"knowledge_context": items}
