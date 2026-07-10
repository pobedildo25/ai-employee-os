from uuid import UUID

from app.repositories.client_repository import ClientRepository
from app.schemas.client import ClientCreate, ClientRead, ClientUpdate


class ClientService:
    def __init__(self, repository: ClientRepository) -> None:
        self._repository = repository

    async def create(self, data: ClientCreate) -> ClientRead:
        client = await self._repository.create(data)
        return ClientRead.model_validate(client)

    async def get_by_id(self, client_id: UUID) -> ClientRead | None:
        client = await self._repository.get_by_id(client_id)
        return ClientRead.model_validate(client) if client else None

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[ClientRead]:
        clients = await self._repository.list_all(skip=skip, limit=limit)
        return [ClientRead.model_validate(client) for client in clients]

    async def update(self, client_id: UUID, data: ClientUpdate) -> ClientRead | None:
        client = await self._repository.update(client_id, data)
        return ClientRead.model_validate(client) if client else None

    async def delete(self, client_id: UUID) -> bool:
        return await self._repository.delete(client_id)
