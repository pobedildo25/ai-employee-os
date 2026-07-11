from abc import ABC, abstractmethod
from uuid import UUID

from app.knowledge.models import KnowledgeItem


class KnowledgeStore(ABC):
    """Storage abstraction for client knowledge — Postgres now, Qdrant-ready later."""

    @abstractmethod
    async def save(self, item: KnowledgeItem) -> KnowledgeItem:
        ...

    @abstractmethod
    async def get_by_id(self, item_id: UUID) -> KnowledgeItem | None:
        ...

    @abstractmethod
    async def list_by_client(self, client_id: UUID, *, limit: int = 50) -> list[KnowledgeItem]:
        ...

    @abstractmethod
    async def search(
        self,
        *,
        client_id: UUID | None = None,
        query: str | None = None,
        category: str | None = None,
        limit: int = 20,
    ) -> list[KnowledgeItem]:
        ...
