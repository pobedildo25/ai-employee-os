"""ConversationStore (in-memory + Redis) unit tests."""

from __future__ import annotations

import asyncio

import pytest

from app.conversation.models import ConversationState, FlowMode, PendingClarification
from app.conversation.redis_store import FSM_KEY, LOCK_KEY, RedisConversationStore
from app.conversation.store import ConversationStore
from app.core.config import Settings


@pytest.mark.asyncio
async def test_inmemory_get_save_get_or_create_clear() -> None:
    store = ConversationStore()
    assert await store.get(1) is None

    state = await store.get_or_create(1, 10)
    assert state.user_id == 1
    assert state.chat_id == 10
    assert state.flow_mode == FlowMode.IDLE

    state.flow_mode = FlowMode.PENDING_CLARIFICATION
    state.pending_clarification = PendingClarification(
        original_goal="КП",
        original_user_input="Сделай КП",
        missing_information=["бюджет"],
    )
    await store.save(state)

    loaded = await store.get(1)
    assert loaded is not None
    assert loaded.flow_mode == FlowMode.PENDING_CLARIFICATION
    assert loaded.pending_clarification is not None
    assert loaded.pending_clarification.original_goal == "КП"

    same = await store.get_or_create(1, 99)
    assert same.chat_id == 99
    assert same.flow_mode == FlowMode.PENDING_CLARIFICATION

    await store.clear_flow(1)
    cleared = await store.get(1)
    assert cleared is not None
    assert cleared.flow_mode == FlowMode.IDLE
    assert cleared.progress_message_id is None


@pytest.mark.asyncio
async def test_inmemory_user_lock_serializes() -> None:
    store = ConversationStore()
    order: list[int] = []

    async def worker(n: int) -> None:
        async with store.user_lock(42):
            order.append(n)
            await asyncio.sleep(0.02)
            order.append(n + 10)

    await asyncio.gather(worker(1), worker(2))
    # One critical section fully completes before the other starts the second write.
    assert order in ([1, 11, 2, 12], [2, 12, 1, 11])


class _FakeRedis:
    """Minimal async Redis stub for RedisConversationStore tests."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._data.get(key)

    async def set(
        self,
        key: str,
        value: str,
        *,
        ex: int | None = None,
        nx: bool = False,
    ) -> bool | None:
        del ex  # TTL not simulated beyond presence
        if nx and key in self._data:
            return False
        self._data[key] = value
        return True

    async def delete(self, key: str) -> int:
        return 1 if self._data.pop(key, None) is not None else 0


@pytest.fixture
def settings() -> Settings:
    return Settings(conversation_fsm_ttl_seconds=3600)


@pytest.mark.asyncio
async def test_redis_store_roundtrip(settings: Settings) -> None:
    client = _FakeRedis()
    store = RedisConversationStore(client, settings)  # type: ignore[arg-type]

    state = ConversationState(
        telegram_user_id=7,
        telegram_chat_id=8,
        flow_mode=FlowMode.WAITING_APPROVAL,
        last_user_input="plan",
    )
    await store.save(state)

    raw = await client.get(FSM_KEY.format(user_id=7))
    assert raw is not None
    assert "telegram_user_id" in raw

    loaded = await store.get(7)
    assert loaded is not None
    assert loaded.flow_mode == FlowMode.WAITING_APPROVAL
    assert loaded.last_user_input == "plan"
    assert loaded.user_id == 7

    created = await store.get_or_create(7, 100)
    assert created.chat_id == 100

    await store.clear_flow(7)
    cleared = await store.get(7)
    assert cleared is not None
    assert cleared.flow_mode == FlowMode.IDLE


@pytest.mark.asyncio
async def test_redis_user_lock_acquire_release(settings: Settings) -> None:
    client = _FakeRedis()
    store = RedisConversationStore(client, settings)  # type: ignore[arg-type]

    async with store.user_lock(5):
        assert await client.get(LOCK_KEY.format(user_id=5)) is not None

    assert await client.get(LOCK_KEY.format(user_id=5)) is None


@pytest.mark.asyncio
async def test_redis_user_lock_serializes(settings: Settings) -> None:
    client = _FakeRedis()
    store = RedisConversationStore(client, settings)  # type: ignore[arg-type]
    order: list[str] = []

    async def worker(name: str) -> None:
        async with store.user_lock(9):
            order.append(f"{name}-enter")
            await asyncio.sleep(0.02)
            order.append(f"{name}-exit")

    await asyncio.gather(worker("a"), worker("b"))
    assert order in (
        ["a-enter", "a-exit", "b-enter", "b-exit"],
        ["b-enter", "b-exit", "a-enter", "a-exit"],
    )


def test_create_conversation_store_falls_back_outside_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.conversation.store import ConversationStore, create_conversation_store

    def _boom(_settings: Settings):
        raise RuntimeError("redis down")

    monkeypatch.setattr("app.database.redis.get_redis_client", _boom)
    store = create_conversation_store(Settings(app_env="development"))
    assert isinstance(store, ConversationStore)


def test_create_conversation_store_raises_in_production_when_redis_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.conversation.store import create_conversation_store

    def _boom(_settings: Settings):
        raise RuntimeError("redis down")

    monkeypatch.setattr("app.database.redis.get_redis_client", _boom)
    with pytest.raises(RuntimeError, match="Redis conversation store is required"):
        create_conversation_store(Settings(app_env="production"))


def test_create_conversation_store_uses_redis_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.conversation.redis_store import RedisConversationStore
    from app.conversation.store import create_conversation_store

    monkeypatch.setattr(
        "app.database.redis.get_redis_client",
        lambda _settings: _FakeRedis(),
    )
    store = create_conversation_store(Settings(app_env="production"))
    assert isinstance(store, RedisConversationStore)
