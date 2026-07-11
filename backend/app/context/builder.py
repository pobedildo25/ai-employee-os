import asyncio
import logging
import time
from typing import Any
from uuid import UUID

from app.agent_runtime.state.models import AgentState
from app.context.models import ContextRequest, ExecutionContext
from app.context.providers.artifact_provider import ArtifactContextProvider
from app.context.providers.base import ContextProvider
from app.context.providers.client_provider import ClientContextProvider
from app.context.providers.history_provider import HistoryProvider, InMemoryHistoryProvider
from app.context.providers.memory_provider import MemoryContextProvider
from app.context.providers.project_provider import ProjectContextProvider
from app.client_intelligence.manager import ClientIntelligenceManager
from app.client_intelligence.providers.intelligence_provider import ClientIntelligenceContextProvider
from app.knowledge.manager import KnowledgeManager
from app.knowledge.providers.knowledge_provider import KnowledgeContextProvider
from app.learning.manager import LearningManager
from app.learning.providers.learning_provider import LearningContextProvider
from app.memory.manager import MemoryManager
from app.repositories.artifact_repository import ArtifactRepository
from app.repositories.client_repository import ClientRepository
from app.repositories.project_repository import ProjectRepository
from app.workspace.context import WorkspaceContextProvider
from app.workspace.service import WorkspaceService

logger = logging.getLogger(__name__)

CONTEXT_BUILDER_NODE = "context_builder"


class ContextBuilder:
    """Collects and assembles execution context from independent providers."""

    def __init__(self, providers: list[ContextProvider]) -> None:
        self._providers = providers

    async def build(
        self,
        *,
        user_input: str,
        client_id: UUID | str | None = None,
        project_id: UUID | str | None = None,
        session_id: str | None = None,
        current_task: dict[str, Any] | None = None,
        preferences: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        trace_id: str = "-",
    ) -> ExecutionContext:
        started = time.perf_counter()
        request = ContextRequest(
            user_input=user_input,
            client_id=_parse_uuid(client_id),
            project_id=_parse_uuid(project_id),
            session_id=session_id,
            current_task=current_task,
            preferences=preferences or {},
            metadata=metadata or {},
            trace_id=trace_id,
        )

        fragments = await asyncio.gather(*(provider.fetch(request) for provider in self._providers))
        merged = _merge_fragments(fragments)

        context = ExecutionContext(
            user_input=user_input,
            current_task=current_task or merged.get("current_task"),
            client_context=merged.get("client_context"),
            project_context=merged.get("project_context"),
            artifact_context=merged.get("artifact_context", []),
            conversation_history=merged.get("conversation_history", []),
            memory_context=merged.get("memory_context", []),
            knowledge_context=merged.get("knowledge_context", []),
            client_intelligence_context=merged.get("client_intelligence_context"),
            learning_context=merged.get("learning_context")
            or merged.get("learning_rules")
            or [],
            workspace_context=merged.get("workspace_context"),
            preferences=preferences or merged.get("preferences", {}),
            metadata=metadata or {},
            extensions={
                **(merged.get("extensions") or {}),
                **(
                    {"learning_rules": merged["learning_rules"]}
                    if merged.get("learning_rules")
                    else {}
                ),
            },
        )

        elapsed_ms = (time.perf_counter() - started) * 1000
        providers_used = [provider.name for provider in self._providers if _provider_contributed(provider.name, merged)]
        context_size = len(context.model_dump_json())

        logger.info(
            "context built | trace_id=%s build_time_ms=%.2f providers=%s context_size=%d",
            trace_id,
            elapsed_ms,
            providers_used,
            context_size,
        )
        return context


class ContextBuilderNode:
    """LangGraph node: builds ExecutionContext before Executive Agent."""

    name = CONTEXT_BUILDER_NODE

    def __init__(self, builder: ContextBuilder) -> None:
        self._builder = builder

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        _log_node(state, self.name, "started")
        hints = state.get("context") or {}
        metadata = state.get("metadata") or {}

        execution_context = await self._builder.build(
            user_input=state.get("user_input", ""),
            client_id=hints.get("client_id"),
            project_id=hints.get("project_id"),
            session_id=metadata.get("session_id"),
            current_task=hints.get("current_task"),
            preferences=hints.get("preferences"),
            metadata=metadata,
            trace_id=state.get("trace_id", "-"),
        )

        update = {
            "current_step": self.name,
            "execution_context": execution_context.model_dump(),
            "context": execution_context.to_prioritized_dict(),
            "status": "context_ready",
        }
        _log_node({**state, **update}, self.name, "completed")
        return update


def create_context_builder(
    *,
    client_repository: ClientRepository | None = None,
    project_repository: ProjectRepository | None = None,
    artifact_repository: ArtifactRepository | None = None,
    history_provider: HistoryProvider | None = None,
    memory_manager: MemoryManager | None = None,
    knowledge_manager: KnowledgeManager | None = None,
    learning_manager: LearningManager | None = None,
    workspace_service: WorkspaceService | None = None,
    client_intelligence_manager: ClientIntelligenceManager | None = None,
) -> ContextBuilder:
    providers: list[ContextProvider] = []

    if client_repository is not None:
        providers.append(ClientContextProvider(client_repository))
    if project_repository is not None:
        providers.append(ProjectContextProvider(project_repository))
    if artifact_repository is not None:
        providers.append(ArtifactContextProvider(artifact_repository))

    providers.append(history_provider or InMemoryHistoryProvider())

    if memory_manager is not None:
        providers.append(MemoryContextProvider(memory_manager))
    if knowledge_manager is not None:
        providers.append(KnowledgeContextProvider(knowledge_manager))

    intelligence_manager = client_intelligence_manager
    if intelligence_manager is None and any(
        item is not None
        for item in (
            client_repository,
            project_repository,
            artifact_repository,
            memory_manager,
            knowledge_manager,
            learning_manager,
            workspace_service,
        )
    ):
        intelligence_manager = ClientIntelligenceManager(
            client_repository=client_repository,
            project_repository=project_repository,
            artifact_repository=artifact_repository,
            memory_manager=memory_manager,
            knowledge_manager=knowledge_manager,
            learning_manager=learning_manager,
            workspace_service=workspace_service,
        )
    if intelligence_manager is not None:
        providers.append(ClientIntelligenceContextProvider(intelligence_manager))

    if learning_manager is not None:
        providers.append(LearningContextProvider(learning_manager))
    if workspace_service is not None:
        providers.append(WorkspaceContextProvider(workspace_service))

    return ContextBuilder(providers)


def _merge_fragments(fragments: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for fragment in fragments:
        for key, value in fragment.items():
            if key == "extensions" and isinstance(value, dict):
                merged.setdefault("extensions", {}).update(value)
            elif value is not None:
                merged[key] = value
    return merged


def _provider_contributed(name: str, merged: dict[str, Any]) -> bool:
    mapping = {
        "client": "client_context",
        "project": "project_context",
        "artifact": "artifact_context",
        "history": "conversation_history",
        "memory": "memory_context",
        "knowledge": "knowledge_context",
        "client_intelligence": "client_intelligence_context",
        "learning": "learning_context",
        "workspace": "workspace_context",
    }
    field = mapping.get(name)
    if field is None:
        return False
    value = merged.get(field)
    return bool(value)


def _parse_uuid(value: UUID | str | None) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except ValueError:
        return None


def _log_node(state: AgentState, node_name: str, status: str) -> None:
    logger.info(
        "graph node execution | execution_id=%s trace_id=%s node_name=%s status=%s",
        state.get("execution_id", "-"),
        state.get("trace_id", "-"),
        node_name,
        status,
    )
