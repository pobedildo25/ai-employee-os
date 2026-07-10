from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client
from app.repositories.client_repository import ClientRepository
from app.schemas.client import ClientCreate, ClientUpdate


class SQLAlchemyClientRepository(ClientRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: ClientCreate) -> Client:
        client = Client(name=data.name, description=data.description)
        self._session.add(client)
        await self._session.flush()
        await self._session.refresh(client)
        return client

    async def get_by_id(self, client_id: UUID) -> Client | None:
        return await self._session.get(Client, client_id)

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[Client]:
        result = await self._session.execute(
            select(Client).offset(skip).limit(limit).order_by(Client.created_at.desc())
        )
        return list(result.scalars().all())

    async def update(self, client_id: UUID, data: ClientUpdate) -> Client | None:
        client = await self.get_by_id(client_id)
        if client is None:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(client, field, value)
        await self._session.flush()
        await self._session.refresh(client)
        return client

    async def delete(self, client_id: UUID) -> bool:
        client = await self.get_by_id(client_id)
        if client is None:
            return False
        await self._session.delete(client)
        await self._session.flush()
        return True
