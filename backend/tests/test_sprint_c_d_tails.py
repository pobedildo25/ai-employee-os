from typing import Any
from uuid import UUID

import pytest

from app.adapters.telegram.polling import TelegramPollingService
from app.adapters.telegram.session import BINDING_KEY, TelegramSessionManager
from app.knowledge.models import KnowledgeItem
from app.knowledge.policies.migration_policy import (
    DEFAULT_MIN_CONFIDENCE,
    select_items_for_persist,
    should_persist_item,
)
from app.security.manager import SecurityManager
from app.security.models import Role
from app.security.providers.redis_provider import RedisSecurityProvider
from app.workspace.manager import WorkspaceManager
from app.workspace.repositories.workspace_repository import InMemoryWorkspaceRepository
from app.workspace.service import WorkspaceService


class FakeRedis:
    """Minimal async Redis stub for unit tests."""

    def __init__(self) -> None:
        self._kv: dict[str, str] = {}
        self._zsets: dict[str, dict[str, float]] = {}
        self._lists: dict[str, list[str]] = {}

    async def get(self, key: str) -> str | None:
        return self._kv.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self._kv[key] = value
        return True

    def pipeline(self) -> "FakeRedisPipeline":
        return FakeRedisPipeline(self)

    async def zadd(self, key: str, mapping: dict[str, float]) -> int:
        bucket = self._zsets.setdefault(key, {})
        bucket.update(mapping)
        return len(mapping)

    async def zrevrange(self, key: str, start: int, end: int) -> list[str]:
        bucket = self._zsets.get(key, {})
        ordered = sorted(bucket.items(), key=lambda item: item[1], reverse=True)
        if end < 0:
            end = len(ordered) - 1
        return [member for member, _ in ordered[start : end + 1]]

    async def rpush(self, key: str, value: str) -> int:
        bucket = self._lists.setdefault(key, [])
        bucket.append(value)
        return len(bucket)

    async def llen(self, key: str) -> int:
        return len(self._lists.get(key, []))

    async def ltrim(self, key: str, start: int, end: int) -> bool:
        bucket = self._lists.get(key, [])
        if end == -1:
            self._lists[key] = bucket[start:]
        else:
            self._lists[key] = bucket[start : end + 1]
        return True

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        bucket = self._lists.get(key, [])
        if end == -1:
            return list(bucket[start:])
        return list(bucket[start : end + 1])


class FakeRedisPipeline:
    def __init__(self, redis: FakeRedis) -> None:
        self._redis = redis
        self._ops: list[tuple] = []

    def set(self, key: str, value: str) -> "FakeRedisPipeline":
        self._ops.append(("set", key, value))
        return self

    def zadd(self, key: str, mapping: dict[str, float]) -> "FakeRedisPipeline":
        self._ops.append(("zadd", key, mapping))
        return self

    async def execute(self) -> list[Any]:
        results = []
        for op in self._ops:
            if op[0] == "set":
                results.append(await self._redis.set(op[1], op[2]))
            elif op[0] == "zadd":
                results.append(await self._redis.zadd(op[1], op[2]))
        self._ops.clear()
        return results


class TrackingSession:
    """Tracks whether a transaction stayed open across process_update."""

    def __init__(self) -> None:
        self.in_txn = False
        self.commits = 0
        self.releases_during_process = 0
        self._processing = False

    def in_transaction(self) -> bool:
        return self.in_txn

    async def commit(self) -> None:
        self.commits += 1
        self.in_txn = False
        if self._processing:
            self.releases_during_process += 1

    async def rollback(self) -> None:
        self.in_txn = False

    async def __aenter__(self) -> "TrackingSession":
        self.in_txn = True
        return self

    async def __aexit__(self, *args) -> None:
        self.in_txn = False


@pytest.mark.asyncio
async def test_polling_releases_db_before_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    session = TrackingSession()

    class Factory:
        def __call__(self):
            return session

    class FakeBot:
        def __init__(self, db_release) -> None:
            self._db_release = db_release

        async def process_update(self, update):
            session._processing = True
            assert session.in_transaction()
            assert self._db_release is not None
            await self._db_release()
            assert not session.in_transaction()
            session._processing = False
            return {"ok": True}

    monkeypatch.setattr(
        "app.adapters.telegram.polling.build_telegram_bot",
        lambda _session, db_release=None, **_kwargs: FakeBot(db_release),
    )

    service = TelegramPollingService()
    await service._dispatch_update(Factory(), {"update_id": 1})
    assert session.commits >= 1
    assert session.releases_during_process >= 1


@pytest.mark.asyncio
async def test_session_bindings_redis_roundtrip() -> None:
    redis = FakeRedis()
    workspace = WorkspaceService(WorkspaceManager(InMemoryWorkspaceRepository()))
    manager = TelegramSessionManager(workspace_service=workspace, redis_client=redis)

    snapshot = await manager.resolve(4242)
    workspace_id = UUID(snapshot["workspace_id"])
    assert await redis.get(BINDING_KEY.format(user_id=4242)) == str(workspace_id)

    other = TelegramSessionManager(
        workspace_service=workspace,
        bindings={},  # explicit in-memory — must not touch Redis
        redis_client=redis,
    )
    assert other.get_bound_workspace_id(4242) is None

    restored = TelegramSessionManager(workspace_service=workspace, redis_client=redis)
    again = await restored.resolve(4242)
    assert again["workspace_id"] == str(workspace_id)


def test_knowledge_min_confidence_raised() -> None:
    assert DEFAULT_MIN_CONFIDENCE >= 0.7
    low = KnowledgeItem(title="t", category="fact", content="c", confidence=0.5)
    high = KnowledgeItem(title="t", category="fact", content="c", confidence=0.8)
    assert should_persist_item(low) is False
    assert should_persist_item(high) is True
    assert select_items_for_persist([high], persist=False) == []
    assert select_items_for_persist([high], persist=True) == [high]
    assert select_items_for_persist([low], confirm=True) == [low]


@pytest.mark.asyncio
async def test_redis_security_provider_with_fake_redis() -> None:
    store = RedisSecurityProvider(FakeRedis())  # type: ignore[arg-type]
    manager = SecurityManager(store)
    created = await manager.create_api_key(name="redis-key", role=Role.USER)
    principal = await manager.validate_api_key(created.api_key)
    assert principal is not None
    assert principal.api_key_id == created.id

    await manager.record_audit(
        actor=f"api_key:{created.id}",
        action="test",
        resource="/x",
        metadata={"token": "secret-token-value"},
    )
    events = await manager.list_audit()
    assert len(events) == 1
    assert events[0].metadata.get("token") == "***"

    revoked = await manager.revoke_api_key(created.id)
    assert revoked is not None
    assert await manager.validate_api_key(created.api_key) is None
