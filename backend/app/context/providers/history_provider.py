import logging
from typing import Any

from app.context.models import ContextRequest
from app.context.providers.base import ContextProvider

logger = logging.getLogger(__name__)


class HistoryProvider(ContextProvider):
    """Base history provider interface."""

    name = "history"


class InMemoryHistoryProvider(HistoryProvider):
    """In-memory conversation history for development and testing."""

    def __init__(self) -> None:
        self._sessions: dict[str, list[dict[str, Any]]] = {}

    async def fetch(self, request: ContextRequest) -> dict[str, Any]:
        if not request.session_id:
            return {"conversation_history": []}
        return {"conversation_history": list(self._sessions.get(request.session_id, []))}

    async def append(self, session_id: str, message: dict[str, Any]) -> None:
        self._sessions.setdefault(session_id, []).append(message)


class RedisHistoryProvider(HistoryProvider):
    """Stub for future Redis-backed conversation history."""

    async def fetch(self, request: ContextRequest) -> dict[str, Any]:
        if request.session_id:
            logger.debug(
                "redis history provider stub | session_id=%s trace_id=%s",
                request.session_id,
                request.trace_id,
            )
        return {"conversation_history": []}
