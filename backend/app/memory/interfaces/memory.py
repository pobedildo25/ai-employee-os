from abc import ABC, abstractmethod
from uuid import UUID

from app.memory.models import MemoryItem, MemorySearchQuery


class MemoryStore(ABC):
    """Unified interface for all memory backends."""

    @abstractmethod
    async def save(self, item: MemoryItem) -> MemoryItem:
        """Persist a memory item."""

    @abstractmethod
    async def get(self, memory_id: UUID) -> MemoryItem | None:
        """Retrieve a memory item by id."""

    @abstractmethod
    async def search(self, query: MemorySearchQuery) -> list[MemoryItem]:
        """Search memory items matching the query."""

    @abstractmethod
    async def delete(self, memory_id: UUID) -> bool:
        """Delete a memory item. Returns True if removed."""

    @abstractmethod
    async def update(self, memory_id: UUID, item: MemoryItem) -> MemoryItem | None:
        """Update an existing memory item."""
