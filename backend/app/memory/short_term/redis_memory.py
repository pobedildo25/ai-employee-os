import json
import logging
from uuid import UUID

import redis.asyncio as aioredis

from app.core.config import Settings
from app.memory.interfaces.memory import MemoryStore
from app.memory.models import MemoryItem, MemorySearchQuery, MemoryType

logger = logging.getLogger(__name__)

SESSION_MESSAGES_KEY = "memory:short:session:{session_id}:messages"
SESSION_TASK_KEY = "memory:short:session:{session_id}:task"
ITEM_KEY = "memory:short:item:{memory_id}"


class RedisShortTermMemory(MemoryStore):
    """Redis-backed short-term memory with TTL."""

    MAX_MESSAGES = 20

    def __init__(self, client: aioredis.Redis, settings: Settings) -> None:
        self._client = client
        self._ttl = settings.redis_memory_ttl

    async def save(self, item: MemoryItem) -> MemoryItem:
        payload = item.model_dump(mode="json")
        ttl = self._resolve_ttl(item)

        if item.session_id and item.metadata.get("kind") == "chat_message":
            key = SESSION_MESSAGES_KEY.format(session_id=item.session_id)
            await self._client.rpush(key, json.dumps(payload))
            await self._client.ltrim(key, -self.MAX_MESSAGES, -1)
            await self._client.expire(key, ttl)
        elif item.session_id and item.metadata.get("kind") == "current_task":
            key = SESSION_TASK_KEY.format(session_id=item.session_id)
            await self._client.set(key, json.dumps(payload), ex=ttl)
        else:
            key = ITEM_KEY.format(memory_id=item.id)
            await self._client.set(key, json.dumps(payload), ex=ttl)

        logger.debug("short-term memory saved | id=%s session_id=%s", item.id, item.session_id)
        return item

    async def get(self, memory_id: UUID) -> MemoryItem | None:
        raw = await self._client.get(ITEM_KEY.format(memory_id=memory_id))
        if raw is None:
            return None
        return MemoryItem.model_validate(json.loads(raw))

    async def search(self, query: MemorySearchQuery) -> list[MemoryItem]:
        if not query.session_id:
            return []

        results: list[MemoryItem] = []
        messages_raw = await self._client.lrange(
            SESSION_MESSAGES_KEY.format(session_id=query.session_id),
            0,
            -1,
        )
        for raw in messages_raw:
            item = MemoryItem.model_validate(json.loads(raw))
            if _matches_query(item, query):
                results.append(item)

        task_raw = await self._client.get(SESSION_TASK_KEY.format(session_id=query.session_id))
        if task_raw:
            task_item = MemoryItem.model_validate(json.loads(task_raw))
            if _matches_query(task_item, query):
                results.append(task_item)

        return results[: query.limit]

    async def delete(self, memory_id: UUID) -> bool:
        deleted = await self._client.delete(ITEM_KEY.format(memory_id=memory_id))
        return deleted > 0

    async def update(self, memory_id: UUID, item: MemoryItem) -> MemoryItem | None:
        existing = await self.get(memory_id)
        if existing is None:
            return None
        updated = item.model_copy(update={"id": memory_id})
        await self.save(updated)
        return updated

    def _resolve_ttl(self, item: MemoryItem) -> int:
        return self._ttl


class InMemoryShortTermMemory(MemoryStore):
    """In-memory short-term memory for tests."""

    MAX_MESSAGES = 20

    def __init__(self, ttl: int = 3600) -> None:
        self._ttl = ttl
        self._items: dict[UUID, MemoryItem] = {}
        self._messages: dict[str, list[MemoryItem]] = {}
        self._tasks: dict[str, MemoryItem] = {}

    async def save(self, item: MemoryItem) -> MemoryItem:
        if item.session_id and item.metadata.get("kind") == "chat_message":
            messages = self._messages.setdefault(item.session_id, [])
            messages.append(item)
            self._messages[item.session_id] = messages[-self.MAX_MESSAGES :]
        elif item.session_id and item.metadata.get("kind") == "current_task":
            self._tasks[item.session_id] = item
        else:
            self._items[item.id] = item
        return item

    async def get(self, memory_id: UUID) -> MemoryItem | None:
        return self._items.get(memory_id)

    async def search(self, query: MemorySearchQuery) -> list[MemoryItem]:
        if not query.session_id:
            return []
        results: list[MemoryItem] = []
        for item in self._messages.get(query.session_id, []):
            if _matches_query(item, query):
                results.append(item)
        task = self._tasks.get(query.session_id)
        if task and _matches_query(task, query):
            results.append(task)
        return results[: query.limit]

    async def delete(self, memory_id: UUID) -> bool:
        return self._items.pop(memory_id, None) is not None

    async def update(self, memory_id: UUID, item: MemoryItem) -> MemoryItem | None:
        if memory_id not in self._items:
            return None
        updated = item.model_copy(update={"id": memory_id})
        self._items[memory_id] = updated
        return updated


def _matches_query(item: MemoryItem, query: MemorySearchQuery) -> bool:
    if query.memory_types and item.type not in query.memory_types:
        return False
    if query.client_id and item.client_id != query.client_id:
        return False
    if query.project_id and item.project_id != query.project_id:
        return False
    if query.query and query.query.lower() not in item.content.lower():
        return False
    return item.type == MemoryType.SHORT_TERM
