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

    async def find_by_name(self, name: str) -> Client | None:
        """Case-insensitive lookup of a BUSINESS client by exact name.

        Default implementation scans ``list_all`` and filters out transport
        (Telegram) identities. Concrete repositories may override with an
        efficient query. Returns ``None`` for blank names or no match.
        """
        from app.clients.classification import is_business_client

        target = (name or "").strip().casefold()
        if not target:
            return None
        clients = await self.list_all(limit=1000)
        for client in clients:
            if not is_business_client(client):
                continue
            if ((getattr(client, "name", "") or "").strip().casefold()) == target:
                return client
        return None

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
