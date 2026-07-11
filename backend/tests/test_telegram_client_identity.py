from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.adapters.telegram.session import TelegramSessionManager, telegram_client_id
from app.analytics.models import AnalyticsRequest
from app.analytics.providers.data_provider import CompositeAnalyticsDataProvider
from app.client_intelligence.manager import ClientIntelligenceManager
from app.clients.classification import (
    TELEGRAM_USER_CLIENT_TYPE,
    is_business_client,
    is_telegram_user_client,
    telegram_user_client_metadata,
)
from app.knowledge.migration import KnowledgeMigrationService
from app.repositories.client_repository import ClientRepository
from app.schemas.client import ClientCreate, ClientUpdate
from app.workspace.manager import WorkspaceManager
from app.workspace.repositories.workspace_repository import InMemoryWorkspaceRepository
from app.workspace.service import WorkspaceService


@dataclass
class StoredClient:
    id: UUID
    name: str
    description: str | None = None
    metadata_: dict[str, Any] | None = None


class InMemoryClientRepository(ClientRepository):
    def __init__(self) -> None:
        self._clients: dict[UUID, StoredClient] = {}

    async def create(self, data: ClientCreate) -> StoredClient:
        client = StoredClient(
            id=uuid4(),
            name=data.name,
            description=data.description,
            metadata_=data.metadata,
        )
        self._clients[client.id] = client
        return client

    async def get_by_id(self, client_id: UUID) -> StoredClient | None:
        return self._clients.get(client_id)

    async def get_or_create_with_id(
        self,
        client_id: UUID,
        *,
        name: str,
        description: str | None = None,
        metadata: dict | None = None,
    ) -> StoredClient:
        existing = await self.get_by_id(client_id)
        if existing is not None:
            return existing
        client = StoredClient(
            id=client_id,
            name=name,
            description=description,
            metadata_=metadata,
        )
        self._clients[client_id] = client
        return client

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[StoredClient]:
        items = list(self._clients.values())
        return items[skip : skip + limit]

    async def update(self, client_id: UUID, data: ClientUpdate) -> StoredClient | None:
        client = await self.get_by_id(client_id)
        if client is None:
            return None
        payload = data.model_dump(exclude_unset=True)
        metadata = payload.pop("metadata", None)
        for key, value in payload.items():
            setattr(client, key, value)
        if metadata is not None:
            client.metadata_ = metadata
        return client

    async def delete(self, client_id: UUID) -> bool:
        return self._clients.pop(client_id, None) is not None


@pytest.fixture
def workspace_service() -> WorkspaceService:
    return WorkspaceService(WorkspaceManager(InMemoryWorkspaceRepository()))


@pytest.fixture
def client_repository() -> InMemoryClientRepository:
    return InMemoryClientRepository()


@pytest.mark.asyncio
async def test_telegram_workspace_creates_transport_client_not_business_client(
    workspace_service: WorkspaceService,
    client_repository: InMemoryClientRepository,
) -> None:
    telegram_user_id = 982967309
    session_manager = TelegramSessionManager(
        workspace_service=workspace_service,
        client_repository=client_repository,
    )

    snapshot = await session_manager.resolve(telegram_user_id)

    client_id = telegram_client_id(telegram_user_id)
    stored = await client_repository.get_by_id(client_id)

    assert stored is not None
    assert stored.metadata_ == telegram_user_client_metadata(telegram_user_id)
    assert stored.metadata_["type"] == TELEGRAM_USER_CLIENT_TYPE
    assert is_telegram_user_client(stored) is True
    assert is_business_client(stored) is False
    assert snapshot["client_id"] == str(client_id)


@pytest.mark.asyncio
async def test_agency_business_client_is_separate_from_telegram_user(
    client_repository: InMemoryClientRepository,
) -> None:
    agency = await client_repository.create(
        ClientCreate(name="NOVA Agency", description="Agency knowledge archive")
    )
    telegram_id = telegram_client_id(777)
    await client_repository.get_or_create_with_id(
        telegram_id,
        name="Telegram 777",
        description="Telegram transport identity (not a business client)",
        metadata=telegram_user_client_metadata(777),
    )

    business_clients = [client for client in await client_repository.list_all() if is_business_client(client)]

    assert len(business_clients) == 1
    assert business_clients[0].id == agency.id
    assert business_clients[0].name == "NOVA Agency"


@pytest.mark.asyncio
async def test_analytics_excludes_telegram_transport_client(
    client_repository: InMemoryClientRepository,
) -> None:
    telegram_id = telegram_client_id(42)
    await client_repository.get_or_create_with_id(
        telegram_id,
        name="Telegram 42",
        metadata=telegram_user_client_metadata(42),
    )
    provider = CompositeAnalyticsDataProvider(client_repository=client_repository)

    dataset = await provider.collect(AnalyticsRequest(client_id=telegram_id))

    assert dataset.clients == []
    assert dataset.sources_used == ["skipped_telegram_user"]


@pytest.mark.asyncio
async def test_client_intelligence_skips_telegram_transport_client(
    client_repository: InMemoryClientRepository,
) -> None:
    telegram_id = telegram_client_id(42)
    await client_repository.get_or_create_with_id(
        telegram_id,
        name="Telegram 42",
        metadata=telegram_user_client_metadata(42),
    )
    manager = ClientIntelligenceManager(client_repository=client_repository)

    result = await manager.build_profile(telegram_id)

    assert result.metadata["status"] == "skipped"
    assert result.metadata["reason"] == "telegram_user"
    assert result.profile.summary == ""


@pytest.mark.asyncio
async def test_knowledge_migration_skips_telegram_transport_client(
    client_repository: InMemoryClientRepository,
) -> None:
    from app.knowledge.manager import KnowledgeManager

    telegram_id = telegram_client_id(42)
    await client_repository.get_or_create_with_id(
        telegram_id,
        name="Telegram 42",
        metadata=telegram_user_client_metadata(42),
    )
    service = KnowledgeMigrationService(
        extractor=object(),  # type: ignore[arg-type]
        manager=KnowledgeManager(),
        client_repository=client_repository,
    )

    result = await service.migrate(
        client_id=telegram_id,
        artifacts=[{"id": str(uuid4()), "name": "doc.pdf"}],
    )

    assert result.extracted_items == []
    assert result.processed_artifacts == []
    assert any("telegram transport client" in warning.lower() for warning in result.warnings)
