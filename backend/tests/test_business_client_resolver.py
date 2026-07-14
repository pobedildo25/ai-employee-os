from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.adapters.telegram.conversation_store import (
    TelegramConversationState,
    TelegramConversationStore,
)
from app.adapters.telegram.flow import TelegramProductFlow
from app.clients.classification import is_business_client, telegram_user_client_metadata
from app.clients.name_extractor import extract_business_subject
from app.clients.resolver import BusinessClientResolver
from app.repositories.client_repository import ClientRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.client import ClientCreate, ClientUpdate
from app.schemas.project import ProjectCreate, ProjectUpdate


@dataclass
class StoredClient:
    id: UUID
    name: str
    description: str | None = None
    metadata_: dict[str, Any] | None = None


@dataclass
class StoredProject:
    id: UUID
    client_id: UUID
    name: str
    description: str | None = None
    status: str = "active"


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
        existing = self._clients.get(client_id)
        if existing is not None:
            return existing
        client = StoredClient(id=client_id, name=name, description=description, metadata_=metadata)
        self._clients[client_id] = client
        return client

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[StoredClient]:
        return list(self._clients.values())[skip : skip + limit]

    async def update(self, client_id: UUID, data: ClientUpdate) -> StoredClient | None:
        return self._clients.get(client_id)

    async def delete(self, client_id: UUID) -> bool:
        return self._clients.pop(client_id, None) is not None


class InMemoryProjectRepository(ProjectRepository):
    def __init__(self) -> None:
        self._projects: dict[UUID, StoredProject] = {}

    async def create(self, data: ProjectCreate) -> StoredProject:
        project = StoredProject(
            id=uuid4(),
            client_id=data.client_id,
            name=data.name,
            description=data.description,
            status=data.status,
        )
        self._projects[project.id] = project
        return project

    async def get_by_id(self, project_id: UUID) -> StoredProject | None:
        return self._projects.get(project_id)

    async def list_by_client(self, client_id: UUID, skip: int = 0, limit: int = 100) -> list[StoredProject]:
        items = [p for p in self._projects.values() if p.client_id == client_id]
        return items[skip : skip + limit]

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[StoredProject]:
        return list(self._projects.values())[skip : skip + limit]

    async def update(self, project_id: UUID, data: ProjectUpdate) -> StoredProject | None:
        return self._projects.get(project_id)

    async def delete(self, project_id: UUID) -> bool:
        return self._projects.pop(project_id, None) is not None


@dataclass
class FakeLLMResponse:
    content: str


@dataclass
class FakeGateway:
    """Returns a canned JSON body from complete()."""

    body: str
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def complete(self, messages, model=None, temperature=0.7, max_tokens=None, metadata=None):
        self.calls.append({"messages": messages, "model": model})
        return FakeLLMResponse(content=self.body)


# --- find_by_name -------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_by_name_case_insensitive_business_only() -> None:
    repo = InMemoryClientRepository()
    business = await repo.create(ClientCreate(name="Яндекс", metadata={"type": "business"}))
    await repo.get_or_create_with_id(
        uuid4(), name="Telegram 42", metadata=telegram_user_client_metadata(42)
    )

    found = await repo.find_by_name("яндекс")

    assert found is not None
    assert found.id == business.id


@pytest.mark.asyncio
async def test_find_by_name_ignores_transport_clients() -> None:
    repo = InMemoryClientRepository()
    await repo.get_or_create_with_id(
        uuid4(), name="Яндекс", metadata=telegram_user_client_metadata(1)
    )

    assert await repo.find_by_name("Яндекс") is None


# --- extractor ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_extractor_llm_primary() -> None:
    gateway = FakeGateway(body='{"business_subject": "Сбер", "is_agency_self": false, "confidence": 0.9}')

    subject = await extract_business_subject("сделай КП для сбербанка", llm_gateway=gateway)

    assert subject.name == "Сбер"
    assert subject.is_usable is True
    assert gateway.calls, "gateway should have been called"


@pytest.mark.asyncio
async def test_extractor_llm_null_subject() -> None:
    gateway = FakeGateway(body='{"business_subject": null, "is_agency_self": false, "confidence": 0.0}')

    subject = await extract_business_subject("какой сегодня курс доллара?", llm_gateway=gateway)

    assert subject.name is None
    assert subject.is_usable is False


@pytest.mark.asyncio
async def test_extractor_heuristic_fallback_no_gateway() -> None:
    subject = await extract_business_subject("сделай КП для Яндекса")

    assert subject.name is not None
    assert subject.name.lower().startswith("яндекс")


@pytest.mark.asyncio
async def test_extractor_agency_self_is_not_usable() -> None:
    gateway = FakeGateway(body='{"business_subject": null, "is_agency_self": true, "confidence": 0.9}')

    subject = await extract_business_subject("расскажи про наше агентство", llm_gateway=gateway)

    assert subject.is_usable is False


# --- resolver -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolver_creates_missing_business_client() -> None:
    clients = InMemoryClientRepository()
    projects = InMemoryProjectRepository()
    gateway = FakeGateway(body='{"business_subject": "Acme", "is_agency_self": false, "confidence": 0.9}')
    resolver = BusinessClientResolver(clients, project_repository=projects, llm_gateway=gateway)

    resolved = await resolver.resolve("заведи клиента Acme и сделай КП")

    assert resolved is not None
    assert resolved.created is True
    assert resolved.name == "Acme"
    stored = await clients.get_by_id(resolved.client_id)
    assert stored is not None
    assert is_business_client(stored) is True
    assert resolved.project_id is not None
    assert resolved.project_created is True


@pytest.mark.asyncio
async def test_resolver_reuses_existing_client_and_project() -> None:
    clients = InMemoryClientRepository()
    projects = InMemoryProjectRepository()
    existing = await clients.create(ClientCreate(name="Acme", metadata={"type": "business"}))
    existing_project = await projects.create(ProjectCreate(client_id=existing.id, name="Acme — общие задачи"))
    gateway = FakeGateway(body='{"business_subject": "Acme", "is_agency_self": false, "confidence": 0.9}')
    resolver = BusinessClientResolver(clients, project_repository=projects, llm_gateway=gateway)

    resolved = await resolver.resolve("сделай КП для Acme")

    assert resolved is not None
    assert resolved.created is False
    assert resolved.client_id == existing.id
    assert resolved.project_id == existing_project.id
    assert resolved.project_created is False
    assert len(await clients.list_all()) == 1


@pytest.mark.asyncio
async def test_resolver_returns_none_without_subject() -> None:
    clients = InMemoryClientRepository()
    gateway = FakeGateway(body='{"business_subject": null, "is_agency_self": false, "confidence": 0.0}')
    resolver = BusinessClientResolver(clients, llm_gateway=gateway)

    resolved = await resolver.resolve("привет, как дела?")

    assert resolved is None
    assert await clients.list_all() == []


# --- flow injection -----------------------------------------------------------


def _make_flow(resolver: BusinessClientResolver | None) -> TelegramProductFlow:
    return TelegramProductFlow(
        runtime=object(),
        session_manager=object(),
        sender=object(),
        conversation_store=TelegramConversationStore(),
        business_client_resolver=resolver,
    )


@pytest.mark.asyncio
async def test_flow_attaches_business_client_to_context() -> None:
    clients = InMemoryClientRepository()
    projects = InMemoryProjectRepository()
    gateway = FakeGateway(body='{"business_subject": "Яндекс", "is_agency_self": false, "confidence": 0.9}')
    resolver = BusinessClientResolver(clients, project_repository=projects, llm_gateway=gateway)
    flow = _make_flow(resolver)

    from app.adapters.telegram.models import TelegramExecutionRequest

    request = TelegramExecutionRequest(
        user_input="сделай КП для Яндекса",
        telegram_user_id=1,
        telegram_chat_id=1,
    )
    convo = TelegramConversationState(telegram_user_id=1, telegram_chat_id=1)
    transport_id = str(uuid4())
    context: dict[str, Any] = {"client_id": transport_id, "channel": "telegram"}

    await flow._attach_business_client(request, convo, context)

    assert context["client_id"] != transport_id
    assert context["business_client_id"] == context["client_id"]
    assert context["client_name"] == "Яндекс"
    assert context.get("project_id")
    assert convo.business_client_name == "Яндекс"


@pytest.mark.asyncio
async def test_flow_without_resolver_leaves_context_untouched() -> None:
    flow = _make_flow(None)

    from app.adapters.telegram.models import TelegramExecutionRequest

    request = TelegramExecutionRequest(
        user_input="сделай КП для Яндекса",
        telegram_user_id=1,
        telegram_chat_id=1,
    )
    convo = TelegramConversationState(telegram_user_id=1, telegram_chat_id=1)
    transport_id = str(uuid4())
    context: dict[str, Any] = {"client_id": transport_id}

    await flow._attach_business_client(request, convo, context)

    assert context["client_id"] == transport_id
    assert "business_client_id" not in context
    assert convo.business_client_id is None
