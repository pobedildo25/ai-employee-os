"""Stage E — Runtime hardening: providers degrade, execution continues."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.adapters.telegram.conversation_store import TelegramConversationStore
from app.adapters.telegram.flow import TelegramProductFlow
from app.adapters.telegram.mapper import TelegramMapper
from app.adapters.telegram.progress import TelegramProgressMessenger
from app.adapters.telegram.sender import InMemoryTelegramSender
from app.adapters.telegram.session import TelegramSessionManager
from app.agent_runtime.state.models import create_initial_state
from app.agents.decision.models import DecisionType
from app.agents.executive.agent import ExecutiveAgent
from app.analytics.analyzer import AnalyticsAnalyzer
from app.analytics.models import AnalyticsDataset, AnalyticsRequest, AnalyticsType
from app.analytics.providers.data_provider import CompositeAnalyticsDataProvider
from app.core.config import Settings
from app.document_intelligence.ast.models import ASTNode, ASTNodeType, DocumentAST
from app.document_renderer.models import OutputFormat, RenderRequest, RenderResult
from app.document_renderer.renderer import DocumentRendererService, RenderArtifactService
from app.learning.extractor import LearningExtractor
from app.learning.models import LearningSignal, LearningSource
from app.llm.exceptions import LLMProviderError
from app.llm.gateway import LLMGateway
from app.memory.long_term.postgres_memory import InMemoryLongTermMemory
from app.memory.manager import create_memory_manager
from app.memory.models import MemoryItem, MemorySearchQuery, MemoryType
from app.memory.semantic.qdrant_memory import QdrantSemanticMemory
from app.memory.short_term.redis_memory import InMemoryShortTermMemory
from app.research.models import ResearchRequest, ResearchType
from app.research.researcher import Researcher
from app.workspace.manager import WorkspaceManager
from app.workspace.repositories.workspace_repository import InMemoryWorkspaceRepository
from app.workspace.service import WorkspaceService
from tests.test_telegram_adapter import SAMPLE_UPDATE
from tests.test_telegram_product_ux import FakeArtifactDelivery, FakeContinuation, StreamableFakeRuntime, build_flow


@pytest.fixture
def settings() -> Settings:
    return Settings(memory_enabled=True, skills_enabled=True, semantic_memory_enabled=True)


class BrokenSemanticMemory:
    async def save(self, item: MemoryItem) -> MemoryItem:
        raise RuntimeError("qdrant down")

    async def get(self, memory_id):
        raise RuntimeError("qdrant down")

    async def search(self, query: MemorySearchQuery) -> list[MemoryItem]:
        raise RuntimeError("qdrant down")

    async def delete(self, memory_id) -> bool:
        raise RuntimeError("qdrant down")

    async def update(self, memory_id, item: MemoryItem) -> MemoryItem | None:
        raise RuntimeError("qdrant down")


class BrokenProvider:
    name = "broken"

    async def search(self, queries, limit=10):
        raise RuntimeError("search unavailable")

    async def fetch(self, url: str):
        raise RuntimeError("fetch unavailable")

    async def extract(self, hit):
        raise RuntimeError("extract unavailable")


class FailingLLMGateway:
    async def complete(self, *args, **kwargs):
        raise LLMProviderError("openrouter unavailable")


class FlakyTelegramSender(InMemoryTelegramSender):
    async def send_message(self, chat_id, text, *, reply_to_message_id=None, reply_markup=None):
        if text == "Думаю…":
            raise RuntimeError("telegram send failed")
        return await super().send_message(
            chat_id,
            text,
            reply_to_message_id=reply_to_message_id,
            reply_markup=reply_markup,
        )

    async def edit_message_text(self, chat_id, message_id, text, *, reply_markup=None):
        raise RuntimeError("telegram edit failed")


@pytest.mark.asyncio
async def test_memory_manager_isolates_broken_semantic_store(settings: Settings) -> None:
    long = InMemoryLongTermMemory()
    manager = create_memory_manager(
        short_term=InMemoryShortTermMemory(ttl=settings.redis_memory_ttl),
        long_term=long,
        semantic=BrokenSemanticMemory(),  # type: ignore[arg-type]
        settings=settings,
    )
    await long.save(
        MemoryItem(type=MemoryType.FACT, content="client prefers tables", importance=0.9)
    )

    results = await manager.recall(MemorySearchQuery(query="knowledge topic", limit=10))
    assert any(item.content == "client prefers tables" for item in results)

    saved = await manager.remember(
        MemoryItem(type=MemoryType.KNOWLEDGE, content="semantic write", importance=0.9)
    )
    assert saved.content == "semantic write"


@pytest.mark.asyncio
async def test_qdrant_init_failure_does_not_raise(settings: Settings) -> None:
    client = MagicMock()
    client.get_collections.side_effect = RuntimeError("connection refused")
    memory = QdrantSemanticMemory(client, settings, ensure_on_init=False)
    assert await memory.search(MemorySearchQuery(query="x", limit=5)) == []
    item = MemoryItem(type=MemoryType.KNOWLEDGE, content="y", importance=0.5)
    assert await memory.save(item) == item


@pytest.mark.asyncio
async def test_research_degrades_on_llm_and_provider_errors() -> None:
    researcher = Researcher(BrokenProvider(), llm_gateway=FailingLLMGateway())  # type: ignore[arg-type]
    result = await researcher.research(
        ResearchRequest(query="market", research_type=ResearchType.MARKET_RESEARCH),
        trace_id="t-research",
    )
    assert result.summary
    assert result.metadata.get("status") == "ready"


@pytest.mark.asyncio
async def test_analytics_degrades_on_llm_error() -> None:
    analyzer = AnalyticsAnalyzer(llm_gateway=FailingLLMGateway())  # type: ignore[arg-type]
    dataset = AnalyticsDataset()
    out = await analyzer.interpret(
        request=AnalyticsRequest(analytics_type=AnalyticsType.CLIENT_PERFORMANCE),
        metrics={"quality": {"pass_rate": 0.9}},
        dataset=dataset,
        heuristic_insights=[],
        trace_id="t-analytics",
    )
    assert "summary" in out
    assert out["recommendations"]


@pytest.mark.asyncio
async def test_analytics_data_provider_isolates_repo_errors() -> None:
    class BrokenClients:
        async def get_by_id(self, client_id):
            raise RuntimeError("db down")

    provider = CompositeAnalyticsDataProvider(client_repository=BrokenClients())  # type: ignore[arg-type]
    dataset = await provider.collect(
        AnalyticsRequest(client_id=str(uuid4()), analytics_type=AnalyticsType.CLIENT_PERFORMANCE)
    )
    assert dataset.clients == []


@pytest.mark.asyncio
async def test_learning_extractor_degrades_on_llm_error() -> None:
    extractor = LearningExtractor(FailingLLMGateway())  # type: ignore[arg-type]
    result = await extractor.extract(
        LearningSignal(text="короче", source=LearningSource.USER_FEEDBACK),
        trace_id="t-learn",
    )
    assert result.should_learn is False
    assert result.rule is None


@pytest.mark.asyncio
async def test_render_storage_failure_returns_bytes() -> None:
    class BrokenArtifactService:
        async def upload_artifact(self, *args, **kwargs):
            raise RuntimeError("minio down")

    class FakeRenderer:
        def validate(self, request: RenderRequest) -> None:
            return None

        def render(self, request: RenderRequest) -> RenderResult:
            return RenderResult(
                output_format=request.output_format,
                mime_type="application/octet-stream",
                file_bytes=b"docx",
                metadata={},
            )

    class PassthroughBuilder:
        def validate_ast(self, document_ast: DocumentAST) -> None:
            return None

    service = RenderArtifactService(
        renderer_service=DocumentRendererService(
            renderers={OutputFormat.DOCX: FakeRenderer()},  # type: ignore[arg-type]
            document_builder=PassthroughBuilder(),  # type: ignore[arg-type]
        ),
        artifact_service=BrokenArtifactService(),  # type: ignore[arg-type]
    )
    ast = DocumentAST(root=ASTNode(node_type=ASTNodeType.DOCUMENT), node_count=1)
    result = await service.render_and_store(
        RenderRequest(
            document_structure=ast,
            output_format=OutputFormat.DOCX,
            client_id=uuid4(),
            project_id=uuid4(),
            name="x.docx",
        )
    )
    assert result.file_bytes == b"docx"
    assert result.artifact_id is None
    assert result.metadata.get("storage_degraded") is True


@pytest.mark.asyncio
async def test_executive_degrades_on_openrouter_outage(settings: Settings) -> None:
    class FailProvider:
        async def chat(self, request):
            raise LLMProviderError("all models down")

    gateway = LLMGateway(FailProvider(), settings=settings)  # type: ignore[arg-type]
    agent = ExecutiveAgent(gateway, max_retries=1)
    result = await agent.analyze(
        create_initial_state(execution_id="e1", trace_id="t1", user_input="Создай КП")
    )
    assert result.decision.action == DecisionType.RESPOND
    assert result.decision.response_message


@pytest.mark.asyncio
async def test_telegram_progress_ui_failure_does_not_abort_execution() -> None:
    sender = FlakyTelegramSender()
    runtime = StreamableFakeRuntime(
        final_state={
            "execution_id": "exec-ui",
            "status": "completed",
            "result": {"message": "Ответ без progress UI"},
            "quality_check": {"passed": True, "score": 0.9},
        },
        stream_events=[
            {
                "orchestration": {
                    "telegram_progress": {
                        "progress_percent": 50,
                        "lines": [{"title": "Шаг", "status_label": "выполняется"}],
                    }
                }
            },
            {
                "executor": {
                    "execution_id": "exec-ui",
                    "status": "completed",
                    "result": {"message": "Ответ без progress UI"},
                    "quality_check": {"passed": True, "score": 0.9},
                }
            },
        ],
    )
    session_manager = TelegramSessionManager(
        workspace_service=WorkspaceService(WorkspaceManager(InMemoryWorkspaceRepository())),
        bindings={},
    )
    store = TelegramConversationStore()
    flow = TelegramProductFlow(
        runtime=runtime,  # type: ignore[arg-type]
        session_manager=session_manager,
        sender=sender,
        conversation_store=store,
        progress_messenger=TelegramProgressMessenger(sender, min_interval_seconds=0.0),
        continuation=FakeContinuation(),  # type: ignore[arg-type]
        artifact_delivery=FakeArtifactDelivery(),  # type: ignore[arg-type]
    )
    flow._executive_agent = build_flow(runtime, session_manager, sender, store)._executive_agent

    request = TelegramMapper().map_update(SAMPLE_UPDATE)
    assert request is not None
    result = await flow.handle_message(request)
    assert result["status"] == "completed"
    assert "Ответ без progress UI" in result["reply"]
