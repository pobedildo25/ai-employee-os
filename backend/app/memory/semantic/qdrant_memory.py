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
    """Qdrant-backed semantic memory with stub embeddings and lazy init."""

    def __init__(
        self,
        client: QdrantClient,
        settings: Settings,
        *,
        ensure_on_init: bool = False,
    ) -> None:
        self._client = client
        self._settings = settings
        self._collection = settings.qdrant_collection
        self._collection_ready: bool | None = None
        if ensure_on_init:
            self._ensure_collection_ready()

    @property
    def enabled(self) -> bool:
        return bool(self._settings.semantic_memory_enabled)

    async def save(self, item: MemoryItem) -> MemoryItem:
        if not self.enabled:
            return item
        if not self._ensure_collection_ready():
            return item
        try:
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
        except Exception as exc:
            logger.warning("qdrant save degraded | id=%s error=%s", item.id, exc)
        return item

    async def get(self, memory_id: UUID) -> MemoryItem | None:
        if not self.enabled:
            return None
        if not self._ensure_collection_ready():
            return None
        try:
            records = self._client.retrieve(
                collection_name=self._collection,
                ids=[str(memory_id)],
                with_payload=True,
            )
        except Exception as exc:
            logger.warning("qdrant get degraded | id=%s error=%s", memory_id, exc)
            return None
        if not records:
            return None
        payload = records[0].payload or {}
        return MemoryItem.model_validate(payload)

    async def search(self, query: MemorySearchQuery) -> list[MemoryItem]:
        if not self.enabled:
            return []
        if not query.query:
            return []
        if not self._ensure_collection_ready():
            return []

        try:
            vector = stub_embed(query.query)
            response = self._client.query_points(
                collection_name=self._collection,
                query=vector,
                limit=query.limit,
                query_filter=_build_filter(query),
                with_payload=True,
            )
        except Exception as exc:
            logger.warning("qdrant search degraded | error=%s", exc)
            return []

        results: list[MemoryItem] = []
        for hit in response.points:
            if hit.payload:
                item = MemoryItem.model_validate(hit.payload)
                if query.memory_types is None or item.type in query.memory_types:
                    results.append(item)
        return results

    async def delete(self, memory_id: UUID) -> bool:
        if not self.enabled:
            return False
        if not self._ensure_collection_ready():
            return False
        try:
            self._client.delete(
                collection_name=self._collection,
                points_selector=qmodels.PointIdsList(points=[str(memory_id)]),
            )
            return True
        except Exception as exc:
            logger.warning("qdrant delete degraded | id=%s error=%s", memory_id, exc)
            return False

    async def update(self, memory_id: UUID, item: MemoryItem) -> MemoryItem | None:
        if not self.enabled:
            return None
        existing = await self.get(memory_id)
        if existing is None:
            return None
        updated = item.model_copy(update={"id": memory_id})
        await self.save(updated)
        return updated

    def _ensure_collection_ready(self) -> bool:
        if self._collection_ready is True:
            return True
        if self._collection_ready is False:
            return False
        try:
            self._ensure_collection()
            self._collection_ready = True
            return True
        except Exception as exc:
            self._collection_ready = False
            logger.warning(
                "qdrant collection unavailable | collection=%s error=%s",
                self._collection,
                exc,
            )
            return False

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
    """In-memory semantic memory for tests and Qdrant fallback."""

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


def create_semantic_memory(settings: Settings, client: QdrantClient | None = None) -> MemoryStore:
    """Build semantic store; fall back to in-memory if Qdrant client cannot be created."""
    if not settings.semantic_memory_enabled:
        logger.info("semantic memory disabled by feature flag")
        return InMemorySemanticMemory()
    try:
        from app.database.qdrant import get_qdrant_client

        qdrant = client or get_qdrant_client(settings)
        return QdrantSemanticMemory(qdrant, settings, ensure_on_init=False)
    except Exception as exc:
        logger.warning("qdrant client unavailable, using in-memory semantic store | error=%s", exc)
        return InMemorySemanticMemory()


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
