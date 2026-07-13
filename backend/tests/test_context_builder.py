from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from app.agent_runtime.checkpoint.manager import InMemoryCheckpointManager
from app.agent_runtime.runtime import AgentRuntime, build_executive_graph
from app.context.builder import ContextBuilder, create_context_builder
from app.context.models import ExecutionContext
from app.context.priority import CONTEXT_PRIORITY, build_prioritized_context, sort_context_keys
from app.context.providers.base import ContextProvider
from app.context.providers.history_provider import InMemoryHistoryProvider, RedisHistoryProvider
from app.context.models import ContextRequest
from app.models.artifact import Artifact
from app.models.client import Client
from app.models.enums import ArtifactStatus
from app.models.project import Project
from app.core.config import Settings
from app.llm.gateway import LLMGateway
from app.llm.models import LLMResponse
from tests.llm_fixtures import creation_ast_json as _creation_ast_json
from tests.llm_fixtures import executive_json as _executive_json
from tests.llm_fixtures import mock_gateway as _mock_gateway
from tests.llm_fixtures import review_json as _review_json


@pytest.fixture
def settings() -> Settings:
    return Settings(
        openrouter_api_key="test-key",
        openrouter_base_url="https://openrouter.ai/api/v1",
        default_llm_model="mock-model",
        fallback_llm_model="fallback-model",
    )


class FakeClientRepository:
    def __init__(self, clients: dict[UUID, Client] | None = None) -> None:
        self._clients = clients or {}

    async def get_by_id(self, client_id: UUID) -> Client | None:
        return self._clients.get(client_id)


class FakeProjectRepository:
    def __init__(self, projects: dict[UUID, Project] | None = None) -> None:
        self._projects = projects or {}

    async def get_by_id(self, project_id: UUID) -> Project | None:
        return self._projects.get(project_id)

    async def list_by_client(self, client_id: UUID, skip: int = 0, limit: int = 100) -> list[Project]:
        matched = [p for p in self._projects.values() if p.client_id == client_id]
        return matched[skip : skip + limit]


class FakeArtifactRepository:
    def __init__(self, artifacts: dict[UUID, list[Artifact]] | None = None) -> None:
        self._artifacts = artifacts or {}

    async def list_by_project(self, project_id: UUID, skip: int = 0, limit: int = 100) -> list[Artifact]:
        return self._artifacts.get(project_id, [])[skip : skip + limit]


class MockContextProvider(ContextProvider):
    name = "mock"

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    async def fetch(self, request: ContextRequest) -> dict:
        return self._payload


@pytest.fixture
def client_id() -> UUID:
    return uuid4()


@pytest.fixture
def project_id() -> UUID:
    return uuid4()


@pytest.fixture
def sample_client(client_id: UUID) -> Client:
    return Client(
        id=client_id,
        name="Acme Corp",
        description="Marketing client",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_project(project_id: UUID, client_id: UUID) -> Project:
    return Project(
        id=project_id,
        client_id=client_id,
        name="Q1 Campaign",
        description="Launch campaign",
        status="active",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_artifact(project_id: UUID, client_id: UUID) -> Artifact:
    return Artifact(
        id=uuid4(),
        client_id=client_id,
        project_id=project_id,
        name="Brand Book",
        artifact_type="document",
        description="Brand guidelines",
        status=ArtifactStatus.COMPLETED,
        storage_path="artifacts/brand.pdf",
        mime_type="application/pdf",
        size=1024,
        metadata_={"pages": 12},
        created_by="user",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def test_execution_context_creation() -> None:
    context = ExecutionContext(
        user_input="Prepare a proposal",
        client_context={"name": "Acme Corp"},
        preferences={"language": "ru"},
    )

    assert context.user_input == "Prepare a proposal"
    assert context.client_context["name"] == "Acme Corp"
    assert context.preferences["language"] == "ru"


def test_priority_ordering() -> None:
    context = ExecutionContext(
        user_input="hello",
        current_task={"title": "task"},
        project_context={"name": "Project"},
        client_context={"name": "Client"},
        artifact_context=[{"name": "doc.pdf"}],
        knowledge_context=[{"title": "Tone", "content": "Formal"}],
        research_context={"summary": "External research"},
        client_intelligence_context={"summary": "B2B SaaS client", "confidence": 0.8},
        learning_context=[{"category": "presentation", "rule": "less text on slides"}],
        preferences={"lang": "ru"},
        conversation_history=[{"role": "user", "content": "hi"}],
    )

    ordered = build_prioritized_context(context)
    assert list(ordered.keys()) == list(CONTEXT_PRIORITY)
    assert ordered["user_input"] == "hello"
    assert ordered["project_context"]["name"] == "Project"
    assert ordered["knowledge_context"][0]["title"] == "Tone"
    assert ordered["learning_context"][0]["category"] == "presentation"


def test_sort_context_keys() -> None:
    keys = ["conversation_history", "user_input", "client_context", "artifact_context"]
    assert sort_context_keys(keys) == [
        "user_input",
        "client_context",
        "artifact_context",
        "conversation_history",
    ]


@pytest.mark.asyncio
async def test_context_builder_collects_data(
    client_id: UUID,
    project_id: UUID,
    sample_client: Client,
    sample_project: Project,
    sample_artifact: Artifact,
) -> None:
    history = InMemoryHistoryProvider()
    await history.append(
        "session-1",
        {"role": "user", "content": "Previous message"},
    )

    builder = create_context_builder(
        client_repository=FakeClientRepository({client_id: sample_client}),
        project_repository=FakeProjectRepository({project_id: sample_project}),
        artifact_repository=FakeArtifactRepository({project_id: [sample_artifact]}),
        history_provider=history,
    )

    context = await builder.build(
        user_input="Create a proposal",
        client_id=client_id,
        project_id=project_id,
        session_id="session-1",
        current_task={"title": "Proposal draft"},
        preferences={"language": "ru"},
        trace_id="trace-ctx",
    )

    assert context.client_context["name"] == "Acme Corp"
    assert context.project_context["name"] == "Q1 Campaign"
    assert len(context.artifact_context) == 1
    assert context.artifact_context[0]["name"] == "Brand Book"
    assert context.conversation_history[0]["content"] == "Previous message"
    assert context.current_task["title"] == "Proposal draft"


@pytest.mark.asyncio
async def test_context_builder_without_ids_uses_history_only() -> None:
    builder = create_context_builder()
    context = await builder.build(user_input="Hello")

    assert context.user_input == "Hello"
    assert context.client_context is None
    assert context.project_context is None
    assert context.artifact_context == []
    assert context.conversation_history == []


@pytest.mark.asyncio
async def test_redis_history_provider_stub() -> None:
    provider = RedisHistoryProvider()
    result = await provider.fetch(
        ContextRequest(user_input="test", session_id="s1", trace_id="t1")
    )
    assert result == {"conversation_history": []}


@pytest.mark.asyncio
async def test_mock_provider_integration() -> None:
    builder = ContextBuilder(
        providers=[
            MockContextProvider({"client_context": {"name": "Mock Client"}}),
            InMemoryHistoryProvider(),
        ]
    )
    context = await builder.build(user_input="Test")
    assert context.client_context == {"name": "Mock Client"}


@pytest.mark.asyncio
async def test_broken_provider_does_not_fail_context_build() -> None:
    class BrokenProvider(ContextProvider):
        name = "memory"

        async def fetch(self, request: ContextRequest) -> dict:
            raise RuntimeError("memory unavailable")

    builder = ContextBuilder(
        providers=[
            BrokenProvider(),
            MockContextProvider({"client_context": {"name": "Still Works"}}),
        ]
    )
    context = await builder.build(user_input="Test task", trace_id="trace-degrade")
    assert context.client_context == {"name": "Still Works"}
    assert context.memory_context == []


@pytest.mark.asyncio
async def test_executive_agent_receives_built_context(settings: Settings, project_id: UUID) -> None:
    gateway, provider = _mock_gateway(
        settings,
        _executive_json(
            goal="создать коммерческое предложение",
            summary="Нужно КП для проекта",
            action="EXECUTE",
            required_capabilities=["document_generation"],
            next_action="execute",
        ),
        _review_json(),
    )
    runtime = AgentRuntime(
        graph=build_executive_graph(gateway, create_context_builder()),
        checkpoint_manager=InMemoryCheckpointManager(),
    )

    result = await runtime.execute(
        "Сделай коммерческое предложение",
        context={
            "project_id": str(project_id),
            "current_task": {"title": "Commercial proposal"},
        },
        metadata={"session_id": "sess-1", "auto_approve": True},
    )

    assert result["execution_context"]["user_input"] == "Сделай коммерческое предложение"
    assert result["execution_context"]["current_task"]["title"] == "Commercial proposal"
    assert result["context"]["user_input"] == "Сделай коммерческое предложение"
    assert provider.calls
    user_message = provider.calls[0].messages[-1].content
    assert "Commercial proposal" in user_message or "current_task" in user_message
