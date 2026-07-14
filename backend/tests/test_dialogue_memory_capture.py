from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.config import Settings
from app.memory.capture import DialogueMemoryCapture
from app.memory.manager import MemoryManager
from app.memory.models import MemoryItem, MemorySearchQuery, MemoryType


class InMemoryStore:
    def __init__(self) -> None:
        self.items: list[MemoryItem] = []

    async def save(self, item: MemoryItem) -> MemoryItem:
        self.items.append(item)
        return item

    async def search(self, query: MemorySearchQuery) -> list[MemoryItem]:
        return list(self.items)

    async def delete(self, memory_id) -> bool:
        before = len(self.items)
        self.items = [i for i in self.items if i.id != memory_id]
        return len(self.items) < before


def _manager(enabled: bool = True) -> tuple[MemoryManager, InMemoryStore]:
    long_term = InMemoryStore()
    manager = MemoryManager(
        short_term=InMemoryStore(),
        long_term=long_term,
        semantic=InMemoryStore(),
        settings=Settings(memory_enabled=enabled),
    )
    return manager, long_term


def test_no_keyword_detect_router() -> None:
    """Memory capture must not expose keyword/imperative Product Decision routing."""
    manager, _ = _manager()
    capture = DialogueMemoryCapture(manager)
    assert not hasattr(capture, "detect")


@pytest.mark.asyncio
async def test_capture_persists_fact() -> None:
    manager, long_term = _manager()
    capture = DialogueMemoryCapture(manager)
    client_id = str(uuid4())

    result = await capture.capture("дедлайн в пятницу", client_id=client_id)

    assert result.stored is True
    assert "Запомнил" in result.reply
    assert len(long_term.items) == 1
    saved = long_term.items[0]
    assert saved.type == MemoryType.FACT
    assert saved.content == "дедлайн в пятницу"
    assert str(saved.client_id) == client_id


@pytest.mark.asyncio
async def test_capture_detects_preference() -> None:
    manager, long_term = _manager()
    capture = DialogueMemoryCapture(manager)

    await capture.capture("клиент предпочитает короткие письма")

    assert long_term.items[0].type == MemoryType.PREFERENCE


@pytest.mark.asyncio
async def test_capture_recall_roundtrip() -> None:
    manager, _ = _manager()
    capture = DialogueMemoryCapture(manager)
    client_id = uuid4()

    await capture.capture("мы работаем с Яндексом", client_id=client_id)
    recalled = await manager.recall(
        MemorySearchQuery(query=None, client_id=client_id, memory_types=[MemoryType.FACT])
    )

    assert any("Яндекс" in item.content for item in recalled)


@pytest.mark.asyncio
async def test_persist_candidates_filters_and_dedupes() -> None:
    manager, long_term = _manager()
    capture = DialogueMemoryCapture(manager)
    candidates = [
        {"type": "FACT", "content": "КП для Яндекса подготовлено", "importance": 0.7},
        {"type": "FACT", "content": "КП для Яндекса подготовлено", "importance": 0.7},  # dup
        {"type": "FACT", "content": "нулевая важность", "importance": 0.0},  # retention reject
        {"type": "PREFERENCE", "content": "клиент любит краткость", "importance": 0.6},
        {"type": "FACT", "content": "эфемерное", "importance": 0.9, "metadata": {"ephemeral": True}},
    ]

    stored = await capture.persist_candidates(candidates)

    assert stored == 2
    contents = {i.content for i in long_term.items}
    assert "КП для Яндекса подготовлено" in contents
    assert "клиент любит краткость" in contents
    assert "нулевая важность" not in contents
    assert "эфемерное" not in contents


@pytest.mark.asyncio
async def test_persist_candidates_noop_when_disabled() -> None:
    manager, long_term = _manager(enabled=False)
    capture = DialogueMemoryCapture(manager)

    stored = await capture.persist_candidates(
        [{"type": "FACT", "content": "что-то", "importance": 0.8}]
    )

    assert stored == 0
    assert long_term.items == []


@pytest.mark.asyncio
async def test_capture_noop_when_disabled() -> None:
    manager, long_term = _manager(enabled=False)
    capture = DialogueMemoryCapture(manager)

    result = await capture.capture("дедлайн в пятницу")

    assert result.stored is False
    assert long_term.items == []
