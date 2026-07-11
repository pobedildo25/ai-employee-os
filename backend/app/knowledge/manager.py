from uuid import UUID

from app.knowledge.models import KnowledgeItem
from app.knowledge.store import KnowledgeStore
from app.knowledge.stores.memory_store import InMemoryKnowledgeStore


class KnowledgeManager:
    """Client Knowledge Base — store, search, and context retrieval."""

    def __init__(self, store: KnowledgeStore | None = None) -> None:
        self._store = store or InMemoryKnowledgeStore()

    async def add(self, item: KnowledgeItem) -> KnowledgeItem:
        return await self._store.save(item)

    async def add_many(self, items: list[KnowledgeItem]) -> list[KnowledgeItem]:
        saved: list[KnowledgeItem] = []
        for item in items:
            saved.append(await self._store.save(item))
        return saved

    async def get(self, item_id: UUID) -> KnowledgeItem | None:
        return await self._store.get_by_id(item_id)

    async def list_for_client(self, client_id: UUID, *, limit: int = 50) -> list[KnowledgeItem]:
        return await self._store.list_by_client(client_id, limit=limit)

    async def search(
        self,
        *,
        client_id: UUID | None = None,
        query: str | None = None,
        category: str | None = None,
        limit: int = 20,
    ) -> list[KnowledgeItem]:
        return await self._store.search(
            client_id=client_id,
            query=query,
            category=category,
            limit=limit,
        )

    async def get_context_for_client(
        self,
        client_id: UUID,
        *,
        query: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Return knowledge fragments for Context Builder."""
        items = await self.search(client_id=client_id, query=query, limit=limit)
        if not items and query:
            items = await self.list_for_client(client_id, limit=limit)
        return [
            {
                "id": str(item.id),
                "title": item.title,
                "category": item.category,
                "content": item.content,
                "confidence": item.confidence,
                "source_artifact_id": str(item.source_artifact_id) if item.source_artifact_id else None,
            }
            for item in items
        ]
