"""Conversation FSM store — in-memory default; Redis via create_conversation_store."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from functools import lru_cache

from app.conversation.models import ConversationState, FlowMode
from app.core.config import Settings

logger = logging.getLogger(__name__)


class ConversationStore:
    """In-memory multi-turn conversation state. Used by tests and as Redis fallback."""

    def __init__(self) -> None:
        self._states: dict[int, ConversationState] = {}
        self._locks: dict[int, asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()

    async def get(self, user_id: int) -> ConversationState | None:
        return self._states.get(user_id)

    async def get_or_create(self, user_id: int, chat_id: int) -> ConversationState:
        existing = self._states.get(user_id)
        if existing is not None:
            existing.chat_id = chat_id
            return existing
        state = ConversationState(
            user_id=user_id,
            chat_id=chat_id,
        )
        self._states[user_id] = state
        return state

    async def save(self, state: ConversationState) -> None:
        state.updated_at = datetime.now()
        self._states[state.user_id] = state

    async def clear_flow(self, user_id: int) -> None:
        state = self._states.get(user_id)
        if state is None:
            return
        state.flow_mode = FlowMode.IDLE
        state.progress_message_id = None
        state.revision_prompted_at = None
        await self.save(state)

    async def reset_dialog(self, user_id: int) -> None:
        """Reset conversation FSM for /new — keep workspace/session bindings."""
        state = self._states.get(user_id)
        if state is None:
            return
        state.flow_mode = FlowMode.IDLE
        state.pending_clarification = None
        state.revision_prompted_at = None
        state.last_agent_state = None
        state.progress_message_id = None
        state.artifact_ids = []
        state.last_user_input = None
        state.last_execution_id = None
        await self.save(state)

    @asynccontextmanager
    async def user_lock(self, user_id: int) -> AsyncIterator[None]:
        lock = await self._get_lock(user_id)
        async with lock:
            yield

    async def _get_lock(self, user_id: int) -> asyncio.Lock:
        async with self._locks_guard:
            lock = self._locks.get(user_id)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[user_id] = lock
            return lock


@lru_cache
def get_conversation_store_singleton() -> ConversationStore:
    """Process-lifetime in-memory store so multi-turn state survives adapter rebuilds in tests/dev."""
    return ConversationStore()


def create_conversation_store(settings: Settings) -> ConversationStore:
    """Redis-backed FSM in production (fail-closed); prefer Redis elsewhere, InMemory OK for tests/dev.

    Return type is annotated as ConversationStore for call-site convenience; Redis store
    implements the same async API (duck-typed).
    """
    try:
        from app.conversation.redis_store import RedisConversationStore
        from app.database.redis import get_redis_client

        store = RedisConversationStore(get_redis_client(settings), settings)
        logger.info("conversation store: RedisConversationStore")
        return store  # type: ignore[return-value]
    except Exception as exc:
        if settings.is_production:
            raise RuntimeError(
                "Redis conversation store is required in production; refusing InMemory fallback"
            ) from exc
        logger.warning(
            "Redis conversation store unavailable, falling back to in-memory | error=%s",
            exc,
        )
        return ConversationStore()
