from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.context.builder import create_context_builder
from app.context.providers.memory_provider import MemoryContextProvider
from app.core.config import Settings
from app.memory.manager import create_memory_manager
from app.memory.models import MemoryItem, MemorySearchQuery, MemoryType
from app.memory.semantic.qdrant_memory import QdrantSemanticMemory, stub_embed
from app.memory.long_term.postgres_memory import InMemoryLongTermMemory
from app.memory.short_term.redis_memory import InMemoryShortTermMemory


@pytest.fixture
def settings() -> Settings:
    return Settings(qdrant_collection="test_knowledge", semantic_memory_enabled=True)


def _mock_qdrant_client(*, points: list | None = None) -> MagicMock:
    client = MagicMock()
    client.get_collections.return_value = MagicMock(collections=[])
    response = MagicMock()
    response.points = points or []
    client.query_points.return_value = response
    return client


@pytest.mark.asyncio
async def test_qdrant_semantic_memory_uses_query_points(settings: Settings) -> None:
    item_id = uuid4()
    payload = {
        "id": str(item_id),
        "type": MemoryType.KNOWLEDGE.value,
        "content": "AI automation proposal template",
        "importance": 0.5,
    }
    point = MagicMock()
    point.payload = payload
    client = _mock_qdrant_client(points=[point])

    memory = QdrantSemanticMemory(client, settings)
    results = await memory.search(
        MemorySearchQuery(query="AI automation", limit=5, memory_types=[MemoryType.KNOWLEDGE])
    )

    client.query_points.assert_called_once()
    call_kwargs = client.query_points.call_args.kwargs
    assert call_kwargs["collection_name"] == settings.qdrant_collection
    assert call_kwargs["limit"] == 5
    assert call_kwargs["with_payload"] is True
    assert len(results) == 1
    assert results[0].content == "AI automation proposal template"


@pytest.mark.asyncio
async def test_broken_semantic_memory_does_not_break_context_builder(settings: Settings) -> None:
    class BrokenSemanticMemory:
        async def save(self, item: MemoryItem) -> MemoryItem:
            return item

        async def get(self, memory_id):
            return None

        async def search(self, query: MemorySearchQuery) -> list[MemoryItem]:
            raise AttributeError("'QdrantClient' object has no attribute 'search'")

        async def delete(self, memory_id) -> bool:
            return True

        async def update(self, memory_id, item: MemoryItem) -> MemoryItem | None:
            return None

    manager = create_memory_manager(
        short_term=InMemoryShortTermMemory(ttl=settings.redis_memory_ttl),
        long_term=InMemoryLongTermMemory(),
        semantic=BrokenSemanticMemory(),  # type: ignore[arg-type]
        settings=settings,
    )
    builder = create_context_builder(memory_manager=manager)

    context = await builder.build(
        user_input="Создай КП для Яндекса",
        client_id=uuid4(),
        trace_id="trace-broken-mem",
    )

    assert context.memory_context == []
    assert context.user_input == "Создай КП для Яндекса"


def test_stub_embed_dimensions() -> None:
    vector = stub_embed("test")
    assert len(vector) == 64
