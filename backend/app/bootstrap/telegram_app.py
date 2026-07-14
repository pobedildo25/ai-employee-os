"""Production Telegram wiring using existing adapters (no new transport layer)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.telegram.bot import TelegramBot
from app.adapters.telegram.factory import create_telegram_bot
from app.agency.profile import build_agency_profile
from app.agent_runtime.runtime import create_agent_runtime
from app.agents.executive.agent import ExecutiveAgent
from app.client_intelligence.analyzer import ClientIntelligenceAnalyzer
from app.client_intelligence.builder import ClientIntelligenceBuilder
from app.client_intelligence.manager import ClientIntelligenceManager
from app.clients.resolver import BusinessClientResolver
from app.clients.work_summary import ClientWorkSummaryService
from app.context.builder import create_context_builder
from app.core.config import Settings, get_settings
from app.database.qdrant import get_qdrant_client
from app.database.redis import get_redis_client
from app.knowledge.manager import KnowledgeManager
from app.knowledge.stores.postgres_store import PostgresKnowledgeStore
from app.learning.manager import LearningManager
from app.learning.providers.postgres_learning_store import PostgresLearningStore
from app.llm.gateway import create_llm_gateway
from app.memory.capture import DialogueMemoryCapture
from app.memory.long_term.postgres_memory import PostgresLongTermMemory
from app.memory.manager import create_memory_manager
from app.memory.semantic.qdrant_memory import QdrantSemanticMemory
from app.memory.short_term.redis_memory import RedisShortTermMemory
from app.orchestration.orchestrator import Orchestrator
from app.orchestration.store import get_execution_store_singleton
from app.repositories.sqlalchemy_artifact_repository import SQLAlchemyArtifactRepository
from app.repositories.sqlalchemy_artifact_version_repository import SQLAlchemyArtifactVersionRepository
from app.repositories.sqlalchemy_client_repository import SQLAlchemyClientRepository
from app.repositories.sqlalchemy_project_repository import SQLAlchemyProjectRepository
from app.research.manager import ResearchManager
from app.services.artifact_service import ArtifactService
from app.skills.registry import create_capability_registry
from app.storage.minio_storage import MinioStorage
from app.workspace.manager import WorkspaceManager
from app.workspace.repositories.workspace_repository import PostgresWorkspaceRepository
from app.workspace.service import WorkspaceService


def build_telegram_bot(session: AsyncSession, settings: Settings | None = None) -> TelegramBot:
    """Build a Telegram bot bound to one DB session (commit per update)."""
    settings = settings or get_settings()
    llm_gateway = create_llm_gateway(settings)
    agency_profile = build_agency_profile(settings)
    client_repository = SQLAlchemyClientRepository(session)
    project_repository = SQLAlchemyProjectRepository(session)
    artifact_repository = SQLAlchemyArtifactRepository(session)
    version_repository = SQLAlchemyArtifactVersionRepository(session)
    storage = MinioStorage(settings)
    artifact_service = ArtifactService(artifact_repository, version_repository, storage)
    memory_manager = create_memory_manager(
        short_term=RedisShortTermMemory(get_redis_client(settings), settings),
        long_term=PostgresLongTermMemory(session),
        semantic=QdrantSemanticMemory(get_qdrant_client(settings), settings),
        settings=settings,
    )
    knowledge_manager = KnowledgeManager(PostgresKnowledgeStore(session))
    learning_manager = LearningManager(PostgresLearningStore(session), llm_gateway=llm_gateway)
    workspace_service = WorkspaceService(WorkspaceManager(PostgresWorkspaceRepository(session)))
    capability_registry = create_capability_registry(settings)
    intelligence_manager = ClientIntelligenceManager(
        analyzer=ClientIntelligenceAnalyzer(llm_gateway),
        builder=ClientIntelligenceBuilder(ClientIntelligenceAnalyzer(llm_gateway)),
        client_repository=client_repository,
        project_repository=project_repository,
        artifact_repository=artifact_repository,
        memory_manager=memory_manager,
        knowledge_manager=knowledge_manager,
        learning_manager=learning_manager,
        workspace_service=workspace_service,
    )
    research_manager = ResearchManager(llm_gateway=llm_gateway)
    context_builder = create_context_builder(
        client_repository=client_repository,
        project_repository=project_repository,
        artifact_repository=artifact_repository,
        memory_manager=memory_manager,
        knowledge_manager=knowledge_manager,
        learning_manager=learning_manager,
        workspace_service=workspace_service,
        client_intelligence_manager=intelligence_manager,
        research_manager=research_manager,
        agency_profile=agency_profile,
    )
    runtime = create_agent_runtime(
        llm_gateway=llm_gateway,
        context_builder=context_builder,
        capability_registry=capability_registry,
        learning_manager=learning_manager,
    )
    orchestrator = Orchestrator(store=get_execution_store_singleton())
    executive_agent = ExecutiveAgent(llm_gateway, capability_registry=capability_registry)
    business_client_resolver = BusinessClientResolver(
        client_repository,
        project_repository=project_repository,
        llm_gateway=llm_gateway,
    )
    memory_capture = DialogueMemoryCapture(memory_manager)
    client_work_summary = ClientWorkSummaryService(
        client_repository,
        project_repository=project_repository,
        artifact_repository=artifact_repository,
    )
    return create_telegram_bot(
        runtime=runtime,
        workspace_service=workspace_service,
        settings=settings,
        artifact_service=artifact_service,
        storage=storage,
        orchestrator=orchestrator,
        client_repository=client_repository,
        executive_agent=executive_agent,
        capability_registry=capability_registry,
        business_client_resolver=business_client_resolver,
        agency_profile=agency_profile,
        memory_capture=memory_capture,
        client_work_summary=client_work_summary,
    )
