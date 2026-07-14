from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache
from typing import TYPE_CHECKING

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.database.session import get_db_session
from app.repositories.artifact_repository import ArtifactRepository
from app.repositories.artifact_version_repository import ArtifactVersionRepository
from app.repositories.client_repository import ClientRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.sqlalchemy_artifact_repository import SQLAlchemyArtifactRepository
from app.repositories.sqlalchemy_artifact_version_repository import SQLAlchemyArtifactVersionRepository
from app.repositories.sqlalchemy_client_repository import SQLAlchemyClientRepository
from app.repositories.sqlalchemy_project_repository import SQLAlchemyProjectRepository
from app.repositories.sqlalchemy_task_repository import SQLAlchemyTaskRepository
from app.repositories.task_repository import TaskRepository
from app.services.artifact_service import ArtifactService
from app.services.client_service import ClientService
from app.services.project_service import ProjectService
from app.services.file_processing_service import FileProcessingService
from app.services.task_service import TaskService
from app.file_processing.processor import FileProcessor
from app.llm.gateway import create_llm_gateway
from app.llm.gateway import LLMGateway
from app.storage.minio_storage import MinioStorage
from app.storage.storage_interface import StorageInterface
from app.agent_runtime.checkpoint.manager import (
    CheckpointManager,
    create_checkpoint_manager,
)
from app.agent_runtime.runtime import AgentRuntime, create_agent_runtime
from app.context.builder import ContextBuilder, create_context_builder
from app.database.redis import get_redis_client
from app.memory.long_term.postgres_memory import PostgresLongTermMemory
from app.memory.manager import MemoryManager, create_memory_manager
from app.memory.semantic.qdrant_memory import create_semantic_memory
from app.memory.short_term.redis_memory import RedisShortTermMemory
from app.knowledge.manager import KnowledgeManager
from app.knowledge.stores.postgres_store import PostgresKnowledgeStore
from app.learning.manager import LearningManager
from app.learning.providers.postgres_learning_store import PostgresLearningStore
from app.skills.registry import CapabilityRegistry, create_capability_registry
from app.task_queue.manager import TaskQueueManager
from app.task_queue.repositories.task_queue_repository import PostgresTaskQueueRepository
from app.workspace.manager import WorkspaceManager
from app.workspace.repositories.workspace_repository import PostgresWorkspaceRepository
from app.workspace.service import WorkspaceService
from app.client_intelligence.manager import ClientIntelligenceManager
from app.analytics.manager import AnalyticsManager
from app.research.manager import ResearchManager


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db_session():
        yield session


if TYPE_CHECKING:
    from app.adapters.telegram.bot import TelegramAdapter, TelegramBot
    from app.observability.manager import ObservabilityManager
    from app.security.manager import SecurityManager


@lru_cache
def get_storage() -> StorageInterface:
    return MinioStorage(get_settings())


def get_client_repository(session: AsyncSession = Depends(get_session)) -> ClientRepository:
    return SQLAlchemyClientRepository(session)


def get_project_repository(session: AsyncSession = Depends(get_session)) -> ProjectRepository:
    return SQLAlchemyProjectRepository(session)


def get_artifact_repository(session: AsyncSession = Depends(get_session)) -> ArtifactRepository:
    return SQLAlchemyArtifactRepository(session)


def get_artifact_version_repository(
    session: AsyncSession = Depends(get_session),
) -> ArtifactVersionRepository:
    return SQLAlchemyArtifactVersionRepository(session)


def get_task_repository(session: AsyncSession = Depends(get_session)) -> TaskRepository:
    return SQLAlchemyTaskRepository(session)


def get_client_service(repository: ClientRepository = Depends(get_client_repository)) -> ClientService:
    return ClientService(repository)


def get_project_service(repository: ProjectRepository = Depends(get_project_repository)) -> ProjectService:
    return ProjectService(repository)


def get_artifact_service(
    repository: ArtifactRepository = Depends(get_artifact_repository),
    version_repository: ArtifactVersionRepository = Depends(get_artifact_version_repository),
    storage: StorageInterface = Depends(get_storage),
) -> ArtifactService:
    return ArtifactService(repository, version_repository, storage)


def get_task_service(repository: TaskRepository = Depends(get_task_repository)) -> TaskService:
    return TaskService(repository)


def get_file_processing_service(
    repository: ArtifactRepository = Depends(get_artifact_repository),
    storage: StorageInterface = Depends(get_storage),
) -> FileProcessingService:
    return FileProcessingService(repository, storage, FileProcessor())


@lru_cache
def get_llm_gateway() -> LLMGateway:
    return create_llm_gateway(get_settings())


@lru_cache
def get_checkpoint_manager() -> CheckpointManager:
    return create_checkpoint_manager(get_settings())


@lru_cache
def get_capability_registry() -> CapabilityRegistry:
    return create_capability_registry(get_settings())


def get_memory_manager(
    session: AsyncSession = Depends(get_session),
) -> MemoryManager:
    settings = get_settings()
    return create_memory_manager(
        short_term=RedisShortTermMemory(get_redis_client(settings), settings),
        long_term=PostgresLongTermMemory(session),
        semantic=create_semantic_memory(settings),
        settings=settings,
    )


def get_knowledge_manager(
    session: AsyncSession = Depends(get_session),
) -> KnowledgeManager:
    return KnowledgeManager(PostgresKnowledgeStore(session))


def get_learning_manager(
    session: AsyncSession = Depends(get_session),
    llm_gateway: LLMGateway = Depends(get_llm_gateway),
) -> LearningManager:
    return LearningManager(PostgresLearningStore(session), llm_gateway=llm_gateway)


def get_workspace_service(
    session: AsyncSession = Depends(get_session),
) -> WorkspaceService:
    return WorkspaceService(WorkspaceManager(PostgresWorkspaceRepository(session)))


def get_task_queue_manager(
    session: AsyncSession = Depends(get_session),
) -> TaskQueueManager:
    return TaskQueueManager(PostgresTaskQueueRepository(session))


def get_client_intelligence_manager(
    client_repository: ClientRepository = Depends(get_client_repository),
    project_repository: ProjectRepository = Depends(get_project_repository),
    artifact_repository: ArtifactRepository = Depends(get_artifact_repository),
    memory_manager: MemoryManager = Depends(get_memory_manager),
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager),
    learning_manager: LearningManager = Depends(get_learning_manager),
    workspace_service: WorkspaceService = Depends(get_workspace_service),
    llm_gateway: LLMGateway = Depends(get_llm_gateway),
) -> ClientIntelligenceManager:
    from app.client_intelligence.analyzer import ClientIntelligenceAnalyzer
    from app.client_intelligence.builder import ClientIntelligenceBuilder

    analyzer = ClientIntelligenceAnalyzer(llm_gateway)
    return ClientIntelligenceManager(
        analyzer=analyzer,
        builder=ClientIntelligenceBuilder(analyzer),
        client_repository=client_repository,
        project_repository=project_repository,
        artifact_repository=artifact_repository,
        memory_manager=memory_manager,
        knowledge_manager=knowledge_manager,
        learning_manager=learning_manager,
        workspace_service=workspace_service,
    )


def get_analytics_manager(
    client_repository: ClientRepository = Depends(get_client_repository),
    project_repository: ProjectRepository = Depends(get_project_repository),
    artifact_repository: ArtifactRepository = Depends(get_artifact_repository),
    task_repository: TaskRepository = Depends(get_task_repository),
    llm_gateway: LLMGateway = Depends(get_llm_gateway),
) -> AnalyticsManager:
    from app.analytics.analyzer import AnalyticsAnalyzer
    from app.analytics.providers.data_provider import CompositeAnalyticsDataProvider
    from app.analytics.query_builder import AnalyticsQueryBuilder

    provider = CompositeAnalyticsDataProvider(
        client_repository=client_repository,
        project_repository=project_repository,
        artifact_repository=artifact_repository,
        task_repository=task_repository,
    )
    return AnalyticsManager(
        query_builder=AnalyticsQueryBuilder(provider),
        analyzer=AnalyticsAnalyzer(llm_gateway),
    )


@lru_cache
def get_research_manager_singleton() -> ResearchManager | None:
    """Process-local research cache so GET /research/{id} can resolve prior runs.

    Disabled ≠ Mock: when research_enabled=False, return None (absent), never a
    mock manager that could report completed success.
    """
    from app.core.config import get_settings
    from app.research.factory import create_research_manager

    settings = get_settings()
    if not settings.research_enabled:
        return None
    return create_research_manager(settings, llm_gateway=create_llm_gateway(settings))


def get_research_manager(
    llm_gateway: LLMGateway = Depends(get_llm_gateway),
) -> ResearchManager | None:
    # Reuse singleton cache. Callers that require research must 503 when None.
    _ = llm_gateway
    return get_research_manager_singleton()


@lru_cache
def get_orchestrator_singleton():
    from app.orchestration.orchestrator import Orchestrator
    from app.orchestration.store import get_execution_store_singleton

    return Orchestrator(store=get_execution_store_singleton())


def get_orchestrator():
    return get_orchestrator_singleton()


def get_context_builder(
    client_repository: ClientRepository = Depends(get_client_repository),
    project_repository: ProjectRepository = Depends(get_project_repository),
    artifact_repository: ArtifactRepository = Depends(get_artifact_repository),
    memory_manager: MemoryManager = Depends(get_memory_manager),
    knowledge_manager: KnowledgeManager = Depends(get_knowledge_manager),
    learning_manager: LearningManager = Depends(get_learning_manager),
    workspace_service: WorkspaceService = Depends(get_workspace_service),
    client_intelligence_manager: ClientIntelligenceManager = Depends(get_client_intelligence_manager),
    research_manager: ResearchManager | None = Depends(get_research_manager),
) -> ContextBuilder:
    return create_context_builder(
        client_repository=client_repository,
        project_repository=project_repository,
        artifact_repository=artifact_repository,
        memory_manager=memory_manager,
        knowledge_manager=knowledge_manager,
        learning_manager=learning_manager,
        workspace_service=workspace_service,
        client_intelligence_manager=client_intelligence_manager,
        research_manager=research_manager,
    )


def get_agent_runtime(
    context_builder=Depends(get_context_builder),
    checkpoint_manager: CheckpointManager = Depends(get_checkpoint_manager),
    llm_gateway: LLMGateway = Depends(get_llm_gateway),
    capability_registry: CapabilityRegistry = Depends(get_capability_registry),
    learning_manager: LearningManager = Depends(get_learning_manager),
) -> AgentRuntime:
    return create_agent_runtime(
        checkpoint_manager=checkpoint_manager,
        llm_gateway=llm_gateway,
        context_builder=context_builder,
        capability_registry=capability_registry,
        learning_manager=learning_manager,
    )


def get_telegram_adapter(
    runtime: AgentRuntime = Depends(get_agent_runtime),
    workspace_service: WorkspaceService = Depends(get_workspace_service),
    artifact_service: ArtifactService = Depends(get_artifact_service),
    storage: StorageInterface = Depends(get_storage),
    orchestrator=Depends(get_orchestrator),
    capability_registry: CapabilityRegistry = Depends(get_capability_registry),
) -> TelegramAdapter:
    from app.adapters.telegram.bot import TelegramAdapter
    from app.adapters.telegram.factory import create_telegram_adapter

    return create_telegram_adapter(
        runtime=runtime,
        workspace_service=workspace_service,
        settings=get_settings(),
        artifact_service=artifact_service,
        storage=storage,
        orchestrator=orchestrator,
        capability_registry=capability_registry,
    )


def get_telegram_bot(
    adapter: TelegramAdapter = Depends(get_telegram_adapter),
) -> TelegramBot:
    from app.adapters.telegram.bot import TelegramBot

    settings = get_settings()
    return TelegramBot(adapter, token=settings.telegram_bot_token or None)


@lru_cache
def get_observability_manager() -> ObservabilityManager:
    from app.observability.manager import ObservabilityManager

    return ObservabilityManager()


def get_security_manager(request: Request) -> SecurityManager:
    manager = getattr(request.app.state, "security_manager", None)
    if manager is None:
        from app.security.manager import SecurityManager

        manager = SecurityManager()
        request.app.state.security_manager = manager
    return manager
