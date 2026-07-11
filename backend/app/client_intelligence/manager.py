from typing import Any
from uuid import UUID

from app.brand_style.profile_manager import BrandProfileManager
from app.client_intelligence.analyzer import ClientIntelligenceAnalyzer
from app.client_intelligence.builder import ClientIntelligenceBuilder
from app.client_intelligence.interfaces.intelligence import ClientIntelligenceManagerInterface
from app.client_intelligence.memory_preparer import prepare_client_intelligence_memory_items
from app.client_intelligence.models import (
    ClientIntelligenceResult,
    ClientIntelligenceSources,
)
from app.client_intelligence.validators.profile_validator import ProfileValidator
from app.knowledge.manager import KnowledgeManager
from app.learning.manager import LearningManager
from app.learning.rules import format_rules_for_context
from app.memory.manager import MemoryManager
from app.memory.models import MemorySearchQuery, MemoryType
from app.repositories.artifact_repository import ArtifactRepository
from app.repositories.client_repository import ClientRepository
from app.repositories.project_repository import ProjectRepository
from app.workspace.service import WorkspaceService


class ClientIntelligenceManager(ClientIntelligenceManagerInterface):
    """Aggregates existing Memory/Knowledge/Learning/Workspace data into ClientProfile."""

    def __init__(
        self,
        *,
        builder: ClientIntelligenceBuilder | None = None,
        analyzer: ClientIntelligenceAnalyzer | None = None,
        validator: ProfileValidator | None = None,
        client_repository: ClientRepository | None = None,
        project_repository: ProjectRepository | None = None,
        artifact_repository: ArtifactRepository | None = None,
        memory_manager: MemoryManager | None = None,
        knowledge_manager: KnowledgeManager | None = None,
        learning_manager: LearningManager | None = None,
        workspace_service: WorkspaceService | None = None,
        brand_profile_manager: BrandProfileManager | None = None,
    ) -> None:
        self._analyzer = analyzer or ClientIntelligenceAnalyzer()
        self._builder = builder or ClientIntelligenceBuilder(self._analyzer)
        self._validator = validator or ProfileValidator()
        self._clients = client_repository
        self._projects = project_repository
        self._artifacts = artifact_repository
        self._memory = memory_manager
        self._knowledge = knowledge_manager
        self._learning = learning_manager
        self._workspace = workspace_service
        self._brands = brand_profile_manager

    async def collect_sources(
        self,
        client_id: UUID | str,
        *,
        execution_context: dict[str, Any] | None = None,
        project_id: UUID | str | None = None,
        user_input: str = "",
    ) -> ClientIntelligenceSources:
        cid = _as_uuid(client_id)
        ctx = execution_context or {}
        sources = ClientIntelligenceSources(
            client_id=str(cid) if cid else str(client_id),
            execution_context=ctx,
            client_context=dict(ctx.get("client_context") or {}),
            memory_items=list(ctx.get("memory_context") or []),
            knowledge_items=list(ctx.get("knowledge_context") or []),
            learning_rules=list(ctx.get("learning_context") or ctx.get("learning_rules") or []),
            workspace=dict(ctx.get("workspace_context") or {}),
        )

        if cid and self._clients is not None and not sources.client_context:
            client = await self._clients.get_by_id(cid)
            if client is not None:
                sources.client_context = {
                    "id": str(client.id),
                    "name": client.name,
                    "description": client.description,
                }

        if cid and self._memory is not None and self._memory.enabled and not sources.memory_items:
            items = await self._memory.recall(
                MemorySearchQuery(
                    query=user_input or None,
                    client_id=cid,
                    project_id=_as_uuid(project_id),
                    memory_types=[
                        MemoryType.FACT,
                        MemoryType.PREFERENCE,
                        MemoryType.DECISION,
                        MemoryType.KNOWLEDGE,
                    ],
                    limit=20,
                )
            )
            sources.memory_items = [
                {
                    "id": str(item.id),
                    "type": item.type.value,
                    "content": item.content,
                    "importance": item.importance,
                    "metadata": item.metadata,
                }
                for item in items
            ]

        if cid and self._knowledge is not None and not sources.knowledge_items:
            knowledge = await self._knowledge.get_context_for_client(
                cid, query=user_input or None, limit=15
            )
            sources.knowledge_items = list(knowledge)

        if cid and self._learning is not None and not sources.learning_rules:
            rules = await self._learning.get_rules(client_id=cid, project_id=_as_uuid(project_id), limit=20)
            sources.learning_rules = format_rules_for_context(rules)

        if cid and self._workspace is not None and not sources.workspace:
            snapshot = await self._workspace.get_snapshot_for_client(cid)
            if snapshot:
                sources.workspace = snapshot

        if cid and self._projects is not None:
            projects = await self._projects.list_by_client(cid, skip=0, limit=20)
            sources.projects = [
                {
                    "id": str(p.id),
                    "name": p.name,
                    "description": p.description,
                    "status": getattr(p.status, "value", p.status),
                }
                for p in projects
            ]
            active_project = sources.workspace.get("active_project_id") or project_id
            if active_project and self._artifacts is not None:
                artifacts = await self._artifacts.list_by_project(_as_uuid(active_project) or UUID(str(active_project)))
                sources.artifacts = [
                    {
                        "id": str(a.id),
                        "name": a.name,
                        "artifact_type": a.artifact_type,
                        "status": getattr(a.status, "value", str(a.status)),
                    }
                    for a in artifacts[:20]
                ]

        if cid and self._brands is not None:
            profiles = self._brands.get_profiles_for_client(cid)
            sources.brand_profiles = [p.model_dump(mode="json") for p in profiles]

        return sources

    async def build_profile(
        self,
        client_id: UUID | str,
        *,
        execution_context: dict[str, Any] | None = None,
        use_llm: bool = False,
        project_id: UUID | str | None = None,
        user_input: str = "",
        trace_id: str = "-",
    ) -> ClientIntelligenceResult:
        sources = await self.collect_sources(
            client_id,
            execution_context=execution_context,
            project_id=project_id,
            user_input=user_input,
        )
        enrichment = {}
        if use_llm:
            enrichment = await self._analyzer.enrich_with_llm(sources, trace_id=trace_id)

        profile = self._builder.build(sources, llm_enrichment=enrichment)
        warnings = self._validator.validate(profile)
        memory_items = prepare_client_intelligence_memory_items(profile)
        return ClientIntelligenceResult(
            profile=profile,
            memory_candidates=[item.model_dump(mode="json") for item in memory_items],
            analysis_warnings=warnings,
            metadata={"status": "ready" if not warnings else "incomplete", "use_llm": use_llm},
        )


def _as_uuid(value: UUID | str | None) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except ValueError:
        return None
