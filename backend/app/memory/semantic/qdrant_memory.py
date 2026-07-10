import hashlib
import logging
from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.core.config import Settings
from app.memory.interfaces.memory import MemoryStore
from app.memory.models import MemoryItem, MemorySearchQuery, MemoryType

logger = logging.getLogger(__name__)

VECTOR_SIZE = 64


def stub_embed(text: str, dimensions: int = VECTOR_SIZE) -> list[float]:
    """Deterministic stub embedding for development — not a real embedding model."""
    digest = hashlib.sha256(text.encode()).digest()
    return [((digest[index % len(digest)] / 255.0) * 2 - 1) for index in range(dimensions)]


class QdrantSemanticMemory(MemoryStore):
    """Qdrant-backed semantic memory with stub embeddings."""

    def __init__(self, client: QdrantClient, settings: Settings) -> None:
        self._client = client
        self._collection = settings.qdrant_collection
        self._ensure_collection()

    async def save(self, item: MemoryItem) -> MemoryItem:
        vector = stub_embed(item.content)
        self._client.upsert(
            collection_name=self._collection,
            points=[
                qmodels.PointStruct(
                    id=str(item.id),
                    vector=vector,
                    payload=item.model_dump(mode="json"),
                )
            ],
        )
        return item

    async def get(self, memory_id: UUID) -> MemoryItem | None:
        records = self._client.retrieve(
            collection_name=self._collection,
            ids=[str(memory_id)],
            with_payload=True,
        )
        if not records:
            return None
        payload = records[0].payload or {}
        return MemoryItem.model_validate(payload)

    async def search(self, query: MemorySearchQuery) -> list[MemoryItem]:
        if not query.query:
            return []

        vector = stub_embed(query.query)
        hits = self._client.search(
            collection_name=self._collection,
            query_vector=vector,
            limit=query.limit,
            query_filter=_build_filter(query),
        )
        results: list[MemoryItem] = []
        for hit in hits:
            if hit.payload:
                item = MemoryItem.model_validate(hit.payload)
                if query.memory_types is None or item.type in query.memory_types:
                    results.append(item)
        return results

    async def delete(self, memory_id: UUID) -> bool:
        self._client.delete(
            collection_name=self._collection,
            points_selector=qmodels.PointIdsList(points=[str(memory_id)]),
        )
        return True

    async def update(self, memory_id: UUID, item: MemoryItem) -> MemoryItem | None:
        existing = await self.get(memory_id)
        if existing is None:
            return None
        updated = item.model_copy(update={"id": memory_id})
        await self.save(updated)
        return updated

    def _ensure_collection(self) -> None:
        collections = self._client.get_collections().collections
        if any(collection.name == self._collection for collection in collections):
            return
        self._client.create_collection(
            collection_name=self._collection,
            vectors_config=qmodels.VectorParams(size=VECTOR_SIZE, distance=qmodels.Distance.COSINE),
        )
        logger.info("qdrant collection created | collection=%s", self._collection)


class InMemorySemanticMemory(MemoryStore):
    """In-memory semantic memory for tests."""

    def __init__(self) -> None:
        self._items: dict[UUID, MemoryItem] = {}

    async def save(self, item: MemoryItem) -> MemoryItem:
        self._items[item.id] = item
        return item

    async def get(self, memory_id: UUID) -> MemoryItem | None:
        return self._items.get(memory_id)

    async def search(self, query: MemorySearchQuery) -> list[MemoryItem]:
        if not query.query:
            return []
        needle = query.query.lower()
        results = [
            item
            for item in self._items.values()
            if needle in item.content.lower()
            and (query.memory_types is None or item.type in query.memory_types)
            and (query.client_id is None or item.client_id == query.client_id)
            and (query.project_id is None or item.project_id == query.project_id)
        ]
        return results[: query.limit]

    async def delete(self, memory_id: UUID) -> bool:
        return self._items.pop(memory_id, None) is not None

    async def update(self, memory_id: UUID, item: MemoryItem) -> MemoryItem | None:
        if memory_id not in self._items:
            return None
        updated = item.model_copy(update={"id": memory_id})
        self._items[memory_id] = updated
        return updated


def _build_filter(query: MemorySearchQuery) -> qmodels.Filter | None:
    conditions: list[qmodels.FieldCondition] = []
    if query.client_id:
        conditions.append(
            qmodels.FieldCondition(
                key="client_id",
                match=qmodels.MatchValue(value=str(query.client_id)),
            )
        )
    if query.project_id:
        conditions.append(
            qmodels.FieldCondition(
                key="project_id",
                match=qmodels.MatchValue(value=str(query.project_id)),
            )
        )
    if not conditions:
        return None
    return qmodels.Filter(must=conditions)
