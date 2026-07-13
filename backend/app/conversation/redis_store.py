"""Redis-backed durable ConversationStore for multi-worker / restart-safe FSM."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime

import redis.asyncio as aioredis

from app.conversation.models import ConversationState, FlowMode
from app.core.config import Settings

logger = logging.getLogger(__name__)

FSM_KEY = "conversation:fsm:{user_id}"
LOCK_KEY = "conversation:lock:{user_id}"
LOCK_TTL_SECONDS = 30
LOCK_WAIT_SECONDS = 30
LOCK_POLL_INTERVAL = 0.05


class RedisConversationStore:
    """Durable FSM state in Redis with per-user distributed lock."""

    def __init__(self, client: aioredis.Redis, settings: Settings) -> None:
        self._client = client
        self._ttl = settings.conversation_fsm_ttl_seconds

    async def get(self, telegram_user_id: int) -> ConversationState | None:
        raw = await self._client.get(FSM_KEY.format(user_id=telegram_user_id))
        if raw is None:
            return None
        return ConversationState.model_validate_json(raw)

    async def get_or_create(self, telegram_user_id: int, telegram_chat_id: int) -> ConversationState:
        existing = await self.get(telegram_user_id)
        if existing is not None:
            existing.telegram_chat_id = telegram_chat_id
            return existing
        state = ConversationState(
            telegram_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
        )
        await self.save(state)
        return state

    async def save(self, state: ConversationState) -> None:
        state.updated_at = datetime.now()
        key = FSM_KEY.format(user_id=state.telegram_user_id)
        await self._client.set(key, state.model_dump_json(), ex=self._ttl)

    async def clear_flow(self, telegram_user_id: int) -> None:
        state = await self.get(telegram_user_id)
        if state is None:
            return
        state.flow_mode = FlowMode.IDLE
        state.progress_message_id = None
        state.revision_prompted_at = None
        await self.save(state)

    @asynccontextmanager
    async def user_lock(self, user_id: int) -> AsyncIterator[None]:
        key = LOCK_KEY.format(user_id=user_id)
        token = uuid.uuid4().hex
        deadline = time.monotonic() + LOCK_WAIT_SECONDS
        while True:
            acquired = await self._client.set(key, token, nx=True, ex=LOCK_TTL_SECONDS)
            if acquired:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(f"conversation lock timeout for user_id={user_id}")
            await asyncio.sleep(LOCK_POLL_INTERVAL)
        try:
            yield
        finally:
            current = await self._client.get(key)
            if current == token:
                await self._client.delete(key)
            else:
                logger.warning(
                    "conversation lock lost or expired before release | user_id=%s",
                    user_id,
                )
