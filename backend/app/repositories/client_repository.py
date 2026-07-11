from abc import ABC, abstractmethod
from uuid import UUID

from app.models.client import Client
from app.schemas.client import ClientCreate, ClientUpdate


class ClientRepository(ABC):
    @abstractmethod
    async def create(self, data: ClientCreate) -> Client:
        ...

    @abstractmethod
    async def get_by_id(self, client_id: UUID) -> Client | None:
        ...

    @abstractmethod
    async def get_or_create_with_id(
        self,
        client_id: UUID,
        *,
        name: str,
        description: str | None = None,
        metadata: dict | None = None,
    ) -> Client:
        ...

    @abstractmethod
    async def list_all(self, skip: int = 0, limit: int = 100) -> list[Client]:
        ...

    @abstractmethod
    async def update(self, client_id: UUID, data: ClientUpdate) -> Client | None:
        ...

    @abstractmethod
    async def delete(self, client_id: UUID) -> bool:
        ...
