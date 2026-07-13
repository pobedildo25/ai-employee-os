import logging
from typing import Any

from app.context.models import ContextRequest
from app.context.providers.base import ContextProvider

logger = logging.getLogger(__name__)

DEFAULT_HISTORY_MAX_MESSAGES = 20


def truncate_conversation_history(
    messages: list[dict[str, Any]],
    max_messages: int,
) -> list[dict[str, Any]]:
    """Keep the last N messages (explicit truncation policy)."""
    if max_messages <= 0:
        return list(messages)
    if len(messages) <= max_messages:
        return list(messages)
    return list(messages[-max_messages:])


class HistoryProvider(ContextProvider):
    """Base history provider interface."""

    name = "history"


class InMemoryHistoryProvider(HistoryProvider):
    """In-memory conversation history for development and testing."""

    def __init__(self, max_messages: int = DEFAULT_HISTORY_MAX_MESSAGES) -> None:
        self._sessions: dict[str, list[dict[str, Any]]] = {}
        self._max_messages = max_messages

    async def fetch(self, request: ContextRequest) -> dict[str, Any]:
        if not request.session_id:
            return {"conversation_history": []}
        messages = list(self._sessions.get(request.session_id, []))
        return {
            "conversation_history": truncate_conversation_history(
                messages, self._max_messages
            )
        }

    async def append(self, session_id: str, message: dict[str, Any]) -> None:
        self._sessions.setdefault(session_id, []).append(message)


class RedisHistoryProvider(HistoryProvider):
    """Stub for future Redis-backed conversation history."""

    def __init__(self, max_messages: int = DEFAULT_HISTORY_MAX_MESSAGES) -> None:
        self._max_messages = max_messages

    async def fetch(self, request: ContextRequest) -> dict[str, Any]:
        if request.session_id:
            logger.debug(
                "redis history provider stub | session_id=%s trace_id=%s",
                request.session_id,
                request.trace_id,
            )
        return {"conversation_history": []}
