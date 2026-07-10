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
from app.skills.builtin.document_skill import DocumentSkill
from app.skills.models import Capability, SkillMetadata
from app.skills.registry import CapabilityRegistry, SkillAlreadyRegisteredError, create_capability_registry
from app.skills.resolver import SkillResolverNode
from tests.llm_fixtures import creation_ast_json as _creation_ast_json
from tests.llm_fixtures import executive_json as _executive_json
from tests.llm_fixtures import mock_gateway as _mock_gateway
from tests.llm_fixtures import plan_json as _plan_json
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


@pytest.fixture
def settings() -> Settings:
    return Settings(skills_enabled=True)


@pytest.fixture
def registry(settings: Settings) -> CapabilityRegistry:
    return create_capability_registry(settings)


def test_skill_registration(registry: CapabilityRegistry) -> None:
    assert registry.get_skill("document_analysis_skill") is not None
    assert registry.get_skill("brand_style_analysis_skill") is not None
    assert registry.get_skill("document_creation_skill") is not None
    assert registry.get_skill("document_render_skill") is not None
    assert registry.get_skill("quality_review_skill") is not None
    assert registry.get_skill("revision_skill") is not None
    assert registry.get_skill("document_skill") is not None
    assert registry.get_skill("analysis_skill") is not None
    assert registry.get_skill("file_skill") is not None


def test_capability_search(registry: CapabilityRegistry) -> None:
    found = registry.find_capabilities(["document_generation", "file_processing"])
    names = {capability.name for capability in found}
    assert names == {"document_generation", "file_processing"}


def test_list_available_capabilities(registry: CapabilityRegistry) -> None:
    capabilities = registry.list_available()
    names = {capability.name for capability in capabilities}
    assert "document_analysis" in names
    assert "data_analysis" in names
    assert "file_extraction" in names


def test_metadata_validation(registry: CapabilityRegistry) -> None:
    skill = registry.get_skill("document_skill")
    assert skill is not None
    metadata = skill.metadata()
    assert metadata.id == "document_skill"
    assert metadata.version == "1.0.0"
    assert "document_generation" in metadata.capabilities
    assert metadata.input_schema
    assert metadata.output_schema


def test_disabled_skill_excluded_from_available(settings: Settings) -> None:
    registry = CapabilityRegistry(settings)
    registry.register(DocumentSkill())
    registry.register(DisabledSkill())

    available = {capability.name for capability in registry.list_available()}
    assert "document_generation" in available
    assert "disabled_capability" not in available


def test_unregister_skill(registry: CapabilityRegistry) -> None:
    assert registry.unregister("file_skill") is True
    assert registry.get_skill("file_skill") is None
    assert registry.find_capabilities(["file_processing"]) == []


def test_duplicate_registration_raises(registry: CapabilityRegistry) -> None:
    with pytest.raises(SkillAlreadyRegisteredError):
        registry.register(DocumentSkill())


@pytest.mark.asyncio
async def test_skill_execute_is_stub(registry: CapabilityRegistry) -> None:
    skill = registry.get_skill("document_skill")
    assert skill is not None
    result = await skill.execute({"content": "test"})
    assert result["status"] == "not_implemented"
    assert result["skill"] == "document_skill"


def test_skill_resolver_node(registry: CapabilityRegistry) -> None:
    node = SkillResolverNode(registry)
    state = create_initial_state(
        execution_id="exec-1",
        trace_id="trace-1",
        user_input="Create a document",
    )
    state["understanding"] = {
        "goal": "create document",
        "summary": "Need document generation",
        "required_capabilities": ["document_generation", "unknown_capability"],
        "missing_information": [],
        "next_action": "execute",
    }

    update = node(state)
    required = update["required_capabilities"]

    assert required["requested"] == ["document_generation", "unknown_capability"]
    assert len(required["resolved"]) == 1
    assert required["resolved"][0]["name"] == "document_generation"
    assert required["unknown"] == ["unknown_capability"]


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
    assert "file_processing" in user_message


@pytest.mark.asyncio
async def test_registry_integration_in_graph(settings: Settings) -> None:
    registry = create_capability_registry(settings)
    gateway, _ = _mock_gateway(
        settings,
        _executive_json(
            goal="анализ данных",
            summary="Нужен анализ",
            action="EXECUTE",
            required_capabilities=["data_analysis"],
            next_action="execute",
        ),
        _plan_json(
            goal="анализ данных",
            steps=[
                {"description": "Analyze data", "capability": "data_analysis", "dependencies": []},
            ],
        ),
        _creation_ast_json(title="Analysis Document"),
        _review_json(),
    )
    runtime = AgentRuntime(
        graph=build_executive_graph(gateway, capability_registry=registry),
        checkpoint_manager=InMemoryCheckpointManager(),
    )

    result = await runtime.execute(
        "Проанализируй данные",
        metadata={"auto_approve": True},
    )

    required = result["required_capabilities"]
    assert required["resolved"][0]["name"] == "data_analysis"
    assert result["document_ast"] is not None
