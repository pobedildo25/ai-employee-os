from typing import Any

from app.context.models import ContextRequest
from app.context.providers.base import ContextProvider
from app.memory.manager import MemoryManager
from app.memory.models import MemorySearchQuery, MemoryType


class MemoryContextProvider(ContextProvider):
    """Recalls relevant memory and injects it into execution context."""

    name = "memory"

    def __init__(self, memory_manager: MemoryManager) -> None:
        self._memory_manager = memory_manager

    async def fetch(self, request: ContextRequest) -> dict[str, Any]:
        if not self._memory_manager.enabled:
            return {}

        query = MemorySearchQuery(
            query=request.user_input,
            client_id=request.client_id,
            project_id=request.project_id,
            session_id=request.session_id,
            memory_types=[
                MemoryType.SHORT_TERM,
                MemoryType.FACT,
                MemoryType.PREFERENCE,
                MemoryType.DECISION,
                MemoryType.KNOWLEDGE,
            ],
            limit=10,
        )
        items = await self._memory_manager.recall(query)
        if not items:
            return {}

        return {
            "memory_context": [
                {
                    "id": str(item.id),
                    "type": item.type.value,
                    "content": item.content,
                    "importance": item.importance,
                    "source": item.source,
                    "metadata": item.metadata,
                }
                for item in items
            ]
        }
