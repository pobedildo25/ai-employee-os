from uuid import uuid4

import pytest

from app.context.builder import create_context_builder
from app.context.models import ContextRequest
from app.context.providers.memory_provider import MemoryContextProvider
from app.core.config import Settings
from app.memory.long_term.postgres_memory import InMemoryLongTermMemory
from app.memory.manager import MemoryManager, MemoryRetentionError, create_memory_manager
from app.memory.models import MemoryItem, MemorySearchQuery, MemoryType
from app.memory.policies.retention import should_persist
from app.memory.semantic.qdrant_memory import InMemorySemanticMemory, stub_embed
from app.memory.short_term.redis_memory import InMemoryShortTermMemory


@pytest.fixture
def settings() -> Settings:
    return Settings(
        memory_enabled=True,
        semantic_memory_enabled=True,
        redis_memory_ttl=3600,
        qdrant_collection="test_knowledge",
    )


@pytest.fixture
def memory_manager(settings: Settings) -> MemoryManager:
    return create_memory_manager(
        short_term=InMemoryShortTermMemory(ttl=settings.redis_memory_ttl),
        long_term=InMemoryLongTermMemory(),
        semantic=InMemorySemanticMemory(),
        settings=settings,
    )


@pytest.mark.asyncio
async def test_short_term_memory_save_and_get(memory_manager: MemoryManager) -> None:
    item = MemoryItem(
        type=MemoryType.SHORT_TERM,
        content="Current task: draft proposal",
        session_id="sess-1",
        metadata={"kind": "current_task"},
    )
    saved = await memory_manager.remember(item)
    recalled = await memory_manager.recall(
        MemorySearchQuery(session_id="sess-1", memory_types=[MemoryType.SHORT_TERM])
    )

    assert saved.id == item.id
    assert len(recalled) == 1
    assert recalled[0].content == "Current task: draft proposal"


@pytest.mark.asyncio
async def test_long_term_memory_fact(memory_manager: MemoryManager, settings: Settings) -> None:
    fact = MemoryItem(
        type=MemoryType.FACT,
        content="Клиент предпочитает минималистичный стиль презентаций",
        importance=0.9,
        source="executive_agent",
        client_id=uuid4(),
    )
    await memory_manager.remember(fact)

    recalled = await memory_manager.recall(
        MemorySearchQuery(
            query="минималистичный",
            memory_types=[MemoryType.FACT],
            client_id=fact.client_id,
        )
    )

    assert len(recalled) == 1
    assert recalled[0].type == MemoryType.FACT


@pytest.mark.asyncio
async def test_semantic_memory_knowledge(memory_manager: MemoryManager) -> None:
    knowledge = MemoryItem(
        type=MemoryType.KNOWLEDGE,
        content="Последний утвержденный формат КП включает блок ROI",
        importance=0.8,
        source="knowledge_base",
    )
    await memory_manager.remember(knowledge)

    recalled = await memory_manager.recall(
        MemorySearchQuery(query="формат КП", memory_types=[MemoryType.KNOWLEDGE])
    )

    assert len(recalled) == 1
    assert recalled[0].type == MemoryType.KNOWLEDGE


@pytest.mark.asyncio
async def test_memory_manager_forget(memory_manager: MemoryManager) -> None:
    item = MemoryItem(
        type=MemoryType.PREFERENCE,
        content="Preferred language: Russian",
        importance=0.7,
    )
    saved = await memory_manager.remember(item)
    deleted = await memory_manager.forget(saved.id, MemoryType.PREFERENCE)

    assert deleted is True
    recalled = await memory_manager.recall(
        MemorySearchQuery(memory_types=[MemoryType.PREFERENCE])
    )
    assert recalled == []


def test_retention_policy_rejects_ephemeral_chat() -> None:
    chat_item = MemoryItem(
        type=MemoryType.FACT,
        content="Hello!",
        importance=0.1,
        metadata={"kind": "chat"},
    )
    assert should_persist(chat_item) is False


def test_retention_policy_accepts_fact() -> None:
    fact = MemoryItem(
        type=MemoryType.FACT,
        content="Client prefers minimal slides",
        importance=0.8,
    )
    assert should_persist(fact) is True


@pytest.mark.asyncio
async def test_memory_manager_rejects_non_persistable_item(memory_manager: MemoryManager) -> None:
    item = MemoryItem(
        type=MemoryType.FACT,
        content="temporary",
        importance=0.0,
        metadata={"ephemeral": True},
    )
    with pytest.raises(MemoryRetentionError):
        await memory_manager.remember(item)


@pytest.mark.asyncio
async def test_memory_context_provider_recall(memory_manager: MemoryManager) -> None:
    await memory_manager.remember(
        MemoryItem(
            type=MemoryType.PREFERENCE,
            content="Клиент предпочитает минималистичный стиль",
            importance=0.85,
            client_id=uuid4(),
        )
    )

    provider = MemoryContextProvider(memory_manager)
    client_id = uuid4()
    await memory_manager.remember(
        MemoryItem(
            type=MemoryType.FACT,
            content="Клиент предпочитает минималистичный стиль презентаций",
            importance=0.9,
            client_id=client_id,
        )
    )

    result = await provider.fetch(
        ContextRequest(
            user_input="Сделай презентацию",
            client_id=client_id,
            trace_id="trace-mem",
        )
    )

    assert "memory_context" in result
    assert len(result["memory_context"]) >= 1
    assert result["memory_context"][0]["type"] in {"FACT", "PREFERENCE"}


@pytest.mark.asyncio
async def test_context_builder_includes_memory_context(memory_manager: MemoryManager) -> None:
    client_id = uuid4()
    await memory_manager.remember(
        MemoryItem(
            type=MemoryType.FACT,
            content="Последний утвержденный формат КП",
            importance=0.9,
            client_id=client_id,
        )
    )

    builder = create_context_builder(memory_manager=memory_manager)
    context = await builder.build(
        user_input="Подготовь КП",
        client_id=client_id,
        trace_id="trace-ctx-mem",
    )

    assert context.memory_context
    assert context.memory_context[0]["content"] == "Последний утвержденный формат КП"
    prioritized = context.to_prioritized_dict()
    assert "memory_context" in prioritized
    assert list(prioritized.keys())[: len(prioritized.keys()) - 1]  # memory appended after priority fields


def test_stub_embed_is_deterministic() -> None:
    first = stub_embed("test content")
    second = stub_embed("test content")
    assert first == second
    assert len(first) == 64


@pytest.mark.asyncio
async def test_memory_disabled(settings: Settings) -> None:
    disabled_settings = settings.model_copy(update={"memory_enabled": False})
    manager = create_memory_manager(
        short_term=InMemoryShortTermMemory(),
        long_term=InMemoryLongTermMemory(),
        semantic=InMemorySemanticMemory(),
        settings=disabled_settings,
    )

    item = MemoryItem(type=MemoryType.FACT, content="Should not persist", importance=0.8)
    await manager.remember(item)
    recalled = await manager.recall(MemorySearchQuery(memory_types=[MemoryType.FACT]))
    assert recalled == []
