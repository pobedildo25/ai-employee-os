from typing import Any

from app.context.models import ContextRequest
from app.context.providers.base import ContextProvider
from app.repositories.client_repository import ClientRepository


class ClientContextProvider(ContextProvider):
    name = "client"

    def __init__(self, repository: ClientRepository) -> None:
        self._repository = repository

    async def fetch(self, request: ContextRequest) -> dict[str, Any]:
        if request.client_id is None:
            return {}

        client = await self._repository.get_by_id(request.client_id)
        if client is None:
            return {}

        return {
            "client_context": {
                "id": str(client.id),
                "name": client.name,
                "description": client.description,
            }
        }
