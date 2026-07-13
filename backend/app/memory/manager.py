import logging
from uuid import UUID

from app.core.config import Settings
from app.memory.interfaces.memory import MemoryStore
from app.memory.models import MemoryItem, MemorySearchQuery, MemoryType
from app.memory.policies.retention import should_persist

logger = logging.getLogger(__name__)


class MemoryError(Exception):
    """Base memory system error."""


class MemoryRetentionError(MemoryError):
    """Raised when an item fails retention policy checks."""


class MemoryManager:
    """Coordinates short-term, long-term, and semantic memory stores."""

    def __init__(
        self,
        short_term: MemoryStore,
        long_term: MemoryStore,
        semantic: MemoryStore,
        settings: Settings,
    ) -> None:
        self._short_term = short_term
        self._long_term = long_term
        self._semantic = semantic
        self._settings = settings

    @property
    def enabled(self) -> bool:
        return self._settings.memory_enabled

    def _store_for_type(self, memory_type: MemoryType) -> MemoryStore:
        if memory_type == MemoryType.SHORT_TERM:
            return self._short_term
        if memory_type == MemoryType.KNOWLEDGE:
            return self._semantic
        return self._long_term

    async def remember(self, item: MemoryItem) -> MemoryItem:
        if not self.enabled:
            logger.debug("memory disabled, skipping remember | id=%s", item.id)
            return item

        if item.type == MemoryType.KNOWLEDGE and not self._settings.semantic_memory_enabled:
            logger.debug("semantic memory disabled, skipping remember | id=%s", item.id)
            return item

        if not should_persist(item):
            raise MemoryRetentionError(f"Memory item rejected by retention policy: {item.type.value}")

        store = self._store_for_type(item.type)
        try:
            saved = await store.save(item)
        except Exception as exc:
            logger.warning(
                "memory remember degraded | id=%s type=%s error=%s",
                item.id,
                item.type.value,
                exc,
            )
            return item
        logger.info(
            "memory remembered | id=%s type=%s source=%s importance=%.2f",
            saved.id,
            saved.type.value,
            saved.source,
            saved.importance,
        )
        return saved

    async def recall(self, query: MemorySearchQuery) -> list[MemoryItem]:
        if not self.enabled:
            return []

        results: list[MemoryItem] = []
        requested_types = set(query.memory_types or list(MemoryType))

        if query.session_id and (not query.memory_types or MemoryType.SHORT_TERM in requested_types):
            short_query = query.model_copy(
                update={"memory_types": [MemoryType.SHORT_TERM], "query": None}
            )
            results.extend(await self._search_store_safe(self._short_term, short_query, "short_term"))

        long_types = requested_types.intersection(
            {MemoryType.FACT, MemoryType.PREFERENCE, MemoryType.DECISION}
        )
        if not query.memory_types or long_types:
            long_query = query.model_copy(
                update={
                    "memory_types": list(long_types) if long_types else None,
                    "query": None,
                }
            )
            results.extend(await self._search_store_safe(self._long_term, long_query, "long_term"))

        if query.query and (not query.memory_types or MemoryType.KNOWLEDGE in requested_types):
            if self._settings.semantic_memory_enabled:
                semantic_query = query.model_copy(
                    update={"memory_types": [MemoryType.KNOWLEDGE]}
                )
                results.extend(await self._search_store_safe(self._semantic, semantic_query, "semantic"))

        return _dedupe_and_limit(results, query.limit)

    async def forget(self, memory_id: UUID, memory_type: MemoryType) -> bool:
        store = self._store_for_type(memory_type)
        try:
            deleted = await store.delete(memory_id)
        except Exception as exc:
            logger.warning(
                "memory forget degraded | id=%s type=%s error=%s",
                memory_id,
                memory_type.value,
                exc,
            )
            return False
        if deleted:
            logger.info("memory forgotten | id=%s type=%s", memory_id, memory_type.value)
        return deleted

    @staticmethod
    async def _search_store_safe(
        store: MemoryStore,
        query: MemorySearchQuery,
        store_name: str,
    ) -> list[MemoryItem]:
        try:
            return await store.search(query)
        except Exception as exc:
            logger.warning("memory recall degraded | store=%s error=%s", store_name, exc)
            return []


def create_memory_manager(
    *,
    short_term: MemoryStore,
    long_term: MemoryStore,
    semantic: MemoryStore,
    settings: Settings | None = None,
) -> MemoryManager:
    from app.core.config import get_settings

    return MemoryManager(
        short_term=short_term,
        long_term=long_term,
        semantic=semantic,
        settings=settings or get_settings(),
    )


def _dedupe_and_limit(items: list[MemoryItem], limit: int) -> list[MemoryItem]:
    seen: set[UUID] = set()
    unique: list[MemoryItem] = []
    for item in sorted(items, key=lambda value: (-value.importance, -value.created_at.timestamp())):
        if item.id in seen:
            continue
        seen.add(item.id)
        unique.append(item)
        if len(unique) >= limit:
            break
    return unique
