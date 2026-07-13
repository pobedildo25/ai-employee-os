import json

import pytest

from app.agent_runtime.checkpoint.manager import InMemoryCheckpointManager
from app.agent_runtime.runtime import AgentRuntime, build_executive_graph
from app.agent_runtime.state.models import create_initial_state
from app.agents.executive.agent import ExecutiveAgent
from app.core.config import Settings
from app.llm.gateway import LLMGateway
from app.llm.models import LLMResponse
from app.skills.base.skill import BaseSkill
from app.skills.models import Capability, SkillMetadata
from app.skills.registry import CapabilityRegistry, SkillAlreadyRegisteredError, create_capability_registry
from app.skills.resolver import SkillResolverNode
from tests.llm_fixtures import creation_ast_json as _creation_ast_json
from tests.llm_fixtures import executive_json as _executive_json
from tests.llm_fixtures import mock_gateway as _mock_gateway
from tests.llm_fixtures import review_json as _review_json


class DisabledSkill(BaseSkill):
    def __init__(self) -> None:
        super().__init__(
            metadata=SkillMetadata(
                id="disabled_skill",
                name="disabled_skill",
                description="Disabled skill",
                capabilities=["disabled_capability"],
                enabled=False,
            ),
            capabilities=[
                Capability(
                    name="disabled_capability",
                    description="Should not appear in list",
                    category="test",
                )
            ],
        )


class _TestOnlyDocumentStub(BaseSkill):
    """Local stub for registry unit tests — not a prod skill module."""

    def __init__(self) -> None:
        super().__init__(
            metadata=SkillMetadata(
                id="test_document_stub",
                name="test_document_stub",
                description="Test-only document stub",
                capabilities=["document_generation"],
            ),
            capabilities=[
                Capability(
                    name="document_generation",
                    description="Создание документов",
                    category="document",
                ),
            ],
        )


@pytest.fixture
def settings() -> Settings:
    return Settings(skills_enabled=True, research_enabled=True, research_allow_mock=True)


@pytest.fixture
def registry(settings: Settings) -> CapabilityRegistry:
    return create_capability_registry(settings)


def test_research_skill_gated_by_flag() -> None:
    off = create_capability_registry(Settings(skills_enabled=True, research_enabled=False))
    on = create_capability_registry(
        Settings(skills_enabled=True, research_enabled=True, research_allow_mock=True)
    )
    assert off.get_skill("research_skill") is None
    assert on.get_skill("research_skill") is not None
    assert "research" not in {c.name for c in off.list_available()}
    assert "research" in {c.name for c in on.list_available()}


def test_skill_registration(registry: CapabilityRegistry) -> None:
    assert registry.get_skill("document_analysis_skill") is not None
    assert registry.get_skill("brand_style_analysis_skill") is not None
    assert registry.get_skill("document_creation_skill") is not None
    assert registry.get_skill("presentation_design_skill") is not None
    assert registry.get_skill("strategy_skill") is not None
    assert registry.get_skill("client_intelligence_skill") is not None
    assert registry.get_skill("analytics_skill") is not None
    assert registry.get_skill("research_skill") is not None
    assert registry.get_skill("document_render_skill") is not None

    assert registry.get_skill("quality_review_skill") is not None
    assert registry.get_skill("revision_skill") is not None
    assert registry.get_skill("knowledge_migration_skill") is not None
    # Stub BaseSkill modules were removed from the tree (L1).
    assert registry.get_skill("document_skill") is None
    assert registry.get_skill("analysis_skill") is None
    assert registry.get_skill("file_skill") is None


def test_capability_search(registry: CapabilityRegistry) -> None:
    found = registry.find_capabilities(
        [
            "document_generation",
            "presentation_design",
            "strategy_analysis",
            "client_intelligence",
            "analytics",
            "research",
        ]
    )
    names = {capability.name for capability in found}
    assert "presentation_design" in names
    assert "strategy_analysis" in names
    assert "client_intelligence" in names
    assert "analytics" in names
    assert "research" in names
    assert "document_generation" in names


def test_list_available_capabilities(registry: CapabilityRegistry) -> None:
    capabilities = registry.list_available()
    names = {capability.name for capability in capabilities}
    assert "document_analysis" in names
    assert "document_generation" in names
    assert "analytics" in names


def test_metadata_validation(registry: CapabilityRegistry) -> None:
    skill = registry.get_skill("document_creation_skill")
    assert skill is not None
    metadata = skill.metadata()
    assert metadata.id == "document_creation_skill"
    assert metadata.version == "1.0.0"
    assert "document_generation" in metadata.capabilities
    assert metadata.input_schema
    assert metadata.output_schema


def test_disabled_skill_excluded_from_available(settings: Settings) -> None:
    registry = CapabilityRegistry(settings)
    registry.register(_TestOnlyDocumentStub())
    registry.register(DisabledSkill())

    available = {capability.name for capability in registry.list_available()}
    assert "document_generation" in available
    assert "disabled_capability" not in available


def test_unregister_skill(registry: CapabilityRegistry) -> None:
    assert registry.unregister("knowledge_migration_skill") is True
    assert registry.get_skill("knowledge_migration_skill") is None


def test_duplicate_registration_raises(registry: CapabilityRegistry) -> None:
    with pytest.raises(SkillAlreadyRegisteredError):
        from app.skills.builtin.strategy_skill import StrategySkill

        registry.register(StrategySkill())


@pytest.mark.asyncio
async def test_stub_skills_not_in_prod_registry(registry: CapabilityRegistry) -> None:
    assert registry.get_skill("document_skill") is None
    skill = registry.get_skill_for_capability("document_generation")
    assert skill is not None
    assert skill.name() == "document_creation_skill"


def test_removed_stub_skill_modules_are_gone() -> None:
    """L1: stub skill files deleted — cannot be imported from app.skills.builtin."""
    import importlib

    for module in (
        "app.skills.builtin.document_skill",
        "app.skills.builtin.analysis_skill",
        "app.skills.builtin.file_skill",
    ):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(module)


def test_skill_resolver_node(registry: CapabilityRegistry) -> None:
    node = SkillResolverNode(registry)
    state = create_initial_state(
        execution_id="exec-1",
        trace_id="trace-1",
        user_input="Create a document",
    )
    state["decision"] = {"action": "EXECUTE"}
    state["understanding"] = {
        "goal": "create document",
        "summary": "Need document generation",
        "required_capabilities": ["document_generation"],
        "missing_information": [],
        "next_action": "execute",
    }

    update = node(state)
    required = update["required_capabilities"]

    assert required["requested"] == ["document_generation"]
    assert [c["name"] for c in required["resolved"]] == [
        "document_generation",
        "document_rendering",
    ]
    assert required["unknown"] == []
    assert update["understanding"]["required_capabilities"] == [
        "document_generation",
        "document_rendering",
    ]


def test_skill_resolver_drops_unknown_capability(registry: CapabilityRegistry) -> None:
    node = SkillResolverNode(registry)
    state = create_initial_state(
        execution_id="exec-1",
        trace_id="trace-1",
        user_input="Create a document",
    )
    state["decision"] = {"action": "EXECUTE"}
    state["understanding"] = {
        "goal": "create document",
        "summary": "Need document generation",
        "required_capabilities": ["document_generation", "unknown_capability"],
        "missing_information": [],
        "next_action": "execute",
    }

    update = node(state)
    assert update["status"] == "capabilities_resolved"
    assert update["understanding"]["required_capabilities"] == [
        "document_generation",
        "document_rendering",
    ]
    assert "unknown_capability" in update["required_capabilities"]["unknown"]


def test_skills_disabled(settings: Settings) -> None:
    disabled_settings = settings.model_copy(update={"skills_enabled": False})
    registry = create_capability_registry(disabled_settings)
    assert registry.list_available() == []
    assert registry.find_capabilities(["document_generation"]) == []


@pytest.mark.asyncio
async def test_executive_agent_receives_available_capabilities(settings: Settings) -> None:
    registry = create_capability_registry(settings)
    gateway, provider = _mock_gateway(
        settings,
        _executive_json(
            goal="создать документ",
            summary="Нужна генерация документа",
            action="CREATE_PLAN",
            required_capabilities=["document_generation"],
            next_action="create_plan",
        ),
    )
    agent = ExecutiveAgent(gateway, capability_registry=registry)
    state = create_initial_state(
        execution_id="exec-1",
        trace_id="trace-1",
        user_input="Создай документ",
    )

    await agent.analyze(state)

    user_message = provider.calls[0].messages[-1].content
    assert "Available capabilities:" in user_message
    assert "document_generation" in user_message
    assert "strategy_analysis" in user_message


@pytest.mark.asyncio
async def test_registry_integration_in_graph(settings: Settings) -> None:
    registry = create_capability_registry(settings)
    gateway, provider = _mock_gateway(
        settings,
        _executive_json(
            goal="анализ документа",
            summary="Нужен анализ",
            action="EXECUTE",
            required_capabilities=["document_analysis"],
            next_action="execute",
        ),
        _review_json(),
    )
    runtime = AgentRuntime(
        graph=build_executive_graph(gateway, capability_registry=registry),
        checkpoint_manager=InMemoryCheckpointManager(),
    )

    result = await runtime.execute("Проанализируй документ")

    required = result["required_capabilities"]
    assert required["resolved"][0]["name"] == "document_analysis"
    assert result["execution_graph"] is None
    assert result["task_plan"]["steps"][0]["capability"] == "document_analysis"
    # document_analysis without extracted_content returns failed — no silent COMPLETED.
    assert result["task_execution"]["status"] == "FAILED"
    assert len(provider.calls) == 1
