from uuid import UUID

from app.knowledge.models import KnowledgeItem
from app.knowledge.store import KnowledgeStore


class InMemoryKnowledgeStore(KnowledgeStore):
    """In-memory knowledge store for tests and local development."""

    def __init__(self) -> None:
        self._items: dict[UUID, KnowledgeItem] = {}

    async def save(self, item: KnowledgeItem) -> KnowledgeItem:
        self._items[item.id] = item
        return item

    async def get_by_id(self, item_id: UUID) -> KnowledgeItem | None:
        return self._items.get(item_id)

    async def list_by_client(self, client_id: UUID, *, limit: int = 50) -> list[KnowledgeItem]:
        results = [item for item in self._items.values() if item.client_id == client_id]
        results.sort(key=lambda item: item.confidence, reverse=True)
        return results[:limit]

    async def search(
        self,
        *,
        client_id: UUID | None = None,
        query: str | None = None,
        category: str | None = None,
        limit: int = 20,
    ) -> list[KnowledgeItem]:
        results = list(self._items.values())
        if client_id is not None:
            results = [item for item in results if item.client_id == client_id]
        if category is not None:
            results = [item for item in results if item.category == category]
        if query:
            needle = query.lower()
            results = [
                item
                for item in results
                if needle in item.title.lower() or needle in item.content.lower()
            ]
        results.sort(key=lambda item: item.confidence, reverse=True)
        return results[:limit]
