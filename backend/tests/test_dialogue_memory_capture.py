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


@pytest.mark.parametrize(
    "text,expected",
    [
        ("запомни, что мы работаем с Яндексом", "мы работаем с Яндексом"),
        ("Запомни: дедлайн в пятницу", "дедлайн в пятницу"),
        ("запиши что клиент любит короткие письма", "клиент любит короткие письма"),
        ("remember that the client prefers PDF", "the client prefers PDF"),
        ("сделай КП для Яндекса", None),
        ("запомни", None),
    ],
)
def test_detect(text: str, expected: str | None) -> None:
    manager, _ = _manager()
    capture = DialogueMemoryCapture(manager)
    assert capture.detect(text) == expected


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
async def test_capture_noop_when_disabled() -> None:
    manager, long_term = _manager(enabled=False)
    capture = DialogueMemoryCapture(manager)

    result = await capture.capture("дедлайн в пятницу")

    assert result.stored is False
    assert long_term.items == []
