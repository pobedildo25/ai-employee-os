from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from app.agent_runtime.checkpoint.manager import InMemoryCheckpointManager
from app.agent_runtime.runtime import AgentRuntime
from app.agent_runtime.state.models import AgentState
from app.context.builder import ContextBuilder, ContextBuilderNode
from app.context.builder import ContextBuilder
from app.context.providers.history_provider import InMemoryHistoryProvider
from app.learning.providers.learning_provider import LearningContextProvider
from app.core.config import Settings
from app.document_creation.creator import DocumentCreator
from app.document_creation.generators.ast_generator import DocumentASTGenerator
from app.document_renderer.renderer import DocumentRendererService, RenderArtifactService
from app.learning.manager import LearningManager
from app.learning.providers.in_memory_learning_store import InMemoryLearningStore
from app.llm.gateway import LLMGateway
from app.services.artifact_service import ArtifactService
from app.skills.builtin.brand_style_analysis_skill import BrandStyleAnalysisSkill
from app.skills.builtin.document_analysis_skill import DocumentAnalysisSkill
from app.skills.builtin.document_creation_skill import DocumentCreationSkill
from app.skills.builtin.document_render_skill import DocumentRenderSkill
from app.skills.builtin.presentation_design_skill import PresentationDesignSkill
from app.skills.builtin.research_skill import ResearchSkill
from app.skills.builtin.revision_skill import RevisionSkill
from app.skills.builtin.strategy_skill import StrategySkill
from app.skills.registry import CapabilityRegistry, create_capability_registry
from app.revision.agent import RevisionAgent
from app.revision.manager import RevisionManager
from tests.test_llm_gateway import MockProvider


def e2e_settings() -> Settings:
    return Settings(skills_enabled=True)


def build_e2e_registry(
    settings: Settings,
    *,
    artifact_service: ArtifactService | None = None,
    llm_gateway: LLMGateway | None = None,
) -> CapabilityRegistry:
    if llm_gateway is None:
        return create_capability_registry(settings)

    registry = CapabilityRegistry(settings)
    creator = DocumentCreator(DocumentASTGenerator(llm_gateway))
    revision_manager = RevisionManager(RevisionAgent(llm_gateway), artifact_service=artifact_service)

    registry.register(DocumentAnalysisSkill())
    registry.register(BrandStyleAnalysisSkill())
    registry.register(DocumentCreationSkill(creator=creator))
    registry.register(PresentationDesignSkill(llm_gateway=llm_gateway))
    registry.register(StrategySkill(llm_gateway=llm_gateway))
    if settings.research_enabled:
        registry.register(
            ResearchSkill(llm_gateway=llm_gateway, allow_mock=settings.research_allow_mock)
        )
    registry.register(
        DocumentRenderSkill(
            artifact_service=RenderArtifactService(
                DocumentRendererService(),
                artifact_service=artifact_service,
            )
            if artifact_service
            else None,
        )
    )
    registry.register(RevisionSkill(manager=revision_manager))

    from app.skills.builtin.analytics_skill import AnalyticsSkill
    from app.skills.builtin.client_intelligence_skill import ClientIntelligenceSkill
    from app.skills.builtin.knowledge_migration_skill import KnowledgeMigrationSkill
    from app.skills.builtin.quality_review_skill import QualityReviewSkill

    registry.register(AnalyticsSkill())
    registry.register(ClientIntelligenceSkill())
    registry.register(QualityReviewSkill())
    registry.register(KnowledgeMigrationSkill())
    return registry


E2E_ATTACHMENT_KEYS = (
    "extracted_content",
    "file_bytes",
    "filename",
    "brand_profile",
    "artifact_id",
)


class E2EContextBuilderNode(ContextBuilderNode):
    """Preserves file and brand attachments from runtime context hints."""

    async def __call__(self, state: AgentState) -> dict[str, object]:
        hints = dict(state.get("context") or {})
        update = await super().__call__(state)
        execution_context = dict(update.get("execution_context") or {})
        for key in E2E_ATTACHMENT_KEYS:
            if key in hints and hints[key] is not None:
                execution_context[key] = hints[key]
        update["execution_context"] = execution_context
        return update


def build_e2e_context_builder(learning_manager: LearningManager) -> ContextBuilder:
    """Minimal context for E2E — avoids empty client intelligence profiles tripping quality gate."""
    return ContextBuilder(
        [
            InMemoryHistoryProvider(),
            LearningContextProvider(learning_manager),
        ]
    )


def build_e2e_runtime(
    gateway: LLMGateway,
    *,
    settings: Settings | None = None,
    artifact_service: ArtifactService | None = None,
    learning_manager: LearningManager | None = None,
) -> tuple[AgentRuntime, CapabilityRegistry, MockProvider]:
    settings = settings or e2e_settings()
    provider = gateway._provider  # type: ignore[attr-defined]
    registry = build_e2e_registry(settings, artifact_service=artifact_service, llm_gateway=gateway)
    learning = learning_manager or LearningManager(InMemoryLearningStore(), llm_gateway=gateway)
    context_builder = build_e2e_context_builder(learning)
    from app.agent_runtime.graph.builder import GraphBuilder
    from app.agent_runtime.graph.edges import wire_executive_workflow
    from app.agent_runtime.graph.nodes import InputNode
    from app.agents.executive.agent import ExecutiveAgent
    from app.agents.executive.node import ChatResponseNode, ExecutiveAgentNode
    from app.document_creation.creator import DocumentCreator
    from app.document_creation.generators.ast_generator import DocumentASTGenerator
    from app.document_creation.nodes.document_creation_node import DocumentCreationNode
    from app.document_creation.nodes.document_render_node import DocumentRenderNode
    from app.orchestration.nodes.orchestration_node import OrchestrationNode
    from app.planning.executor import TaskExecutor
    from app.planning.nodes.executor_node import ExecutorNode
    from app.planning.nodes.planner_node import PlannerNode
    from app.planning.planner import TaskPlanner
    from app.quality.gate import QualityGate
    from app.quality.nodes.quality_gate_node import QualityGateNode
    from app.quality.reviewer import ReviewerAgent
    from app.revision.agent import RevisionAgent
    from app.revision.manager import RevisionManager
    from app.revision.nodes.revision_node import RevisionNode
    from app.skills.resolver import SkillResolverNode

    agent = ExecutiveAgent(gateway, capability_registry=registry)
    planner = TaskPlanner(gateway)
    document_creator = DocumentCreator(DocumentASTGenerator(gateway))
    builder = GraphBuilder()
    builder.add_node(InputNode())
    builder.add_node(E2EContextBuilderNode(context_builder))
    builder.add_node(ExecutiveAgentNode(agent))
    builder.add_node(ChatResponseNode())
    builder.add_node(SkillResolverNode(registry))
    builder.add_node(PlannerNode(planner, registry))
    builder.add_node(OrchestrationNode())
    builder.add_node(ExecutorNode(TaskExecutor(), registry))
    builder.add_node(DocumentCreationNode(document_creator, registry))
    builder.add_node(DocumentRenderNode())
    builder.add_node(QualityGateNode(QualityGate(ReviewerAgent(gateway))))
    builder.add_node(RevisionNode(RevisionManager(RevisionAgent(gateway)), learning_manager=learning))
    wire_executive_workflow(builder)
    runtime = AgentRuntime(
        graph=builder.build(checkpoint_manager=InMemoryCheckpointManager()),
        checkpoint_manager=InMemoryCheckpointManager(),
    )
    return runtime, registry, provider


def brand_plan_steps() -> list[dict[str, Any]]:
    return [
        {"description": "Analyze brand materials", "capability": "document_analysis", "dependencies": []},
        {"description": "Extract brand style", "capability": "brand_style_analysis", "dependencies": [0]},
        {"description": "Create commercial proposal", "capability": "document_creation", "dependencies": [1]},
        {"description": "Render branded document", "capability": "document_rendering", "dependencies": [2]},
    ]


def marketing_plan_steps() -> list[dict[str, Any]]:
    return [
        {"description": "Market research", "capability": "research", "dependencies": []},
        {"description": "Strategy analysis", "capability": "strategy_analysis", "dependencies": [0]},
        {"description": "Presentation design", "capability": "presentation_design", "dependencies": [1]},
        {"description": "Render presentation", "capability": "document_rendering", "dependencies": [2]},
    ]


def new_client_project_ids() -> tuple[UUID, UUID]:
    return uuid4(), uuid4()
