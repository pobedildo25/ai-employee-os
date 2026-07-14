"""Stage C — Planner / Orchestrator minimization regression."""

from __future__ import annotations

import pytest

from app.agent_runtime.checkpoint.manager import InMemoryCheckpointManager
from app.agent_runtime.runtime import AgentRuntime, build_executive_graph
from app.agent_runtime.state.models import create_initial_state
from app.core.config import Settings
from app.orchestration.nodes.orchestration_node import OrchestrationNode
from app.planning.direct_plan import build_direct_execution_plan
from app.planning.nodes.planner_node import PlannerNode
from app.planning.planner import TaskPlanner
from app.planning.policies.execution_policy import (
    plan_requires_orchestration,
    should_invoke_llm_planner,
    should_plan,
)
from app.skills.registry import create_capability_registry
from tests.llm_fixtures import executive_json as _executive_json
from tests.llm_fixtures import mock_gateway as _mock_gateway
from tests.llm_fixtures import plan_json as _plan_json
from tests.llm_fixtures import review_json as _review_json


@pytest.fixture
def settings() -> Settings:
    return Settings(skills_enabled=True)


def test_llm_planner_not_triggered_by_capability_count() -> None:
    assert should_invoke_llm_planner("CREATE_PLAN", []) is False
    assert should_invoke_llm_planner("CREATE_PLAN", ["strategy_analysis"]) is False
    # Linear multi-skill is NOT enough for LLM TaskPlanner.
    assert should_invoke_llm_planner(
        "CREATE_PLAN", ["strategy_analysis", "presentation_design"]
    ) is False
    assert should_invoke_llm_planner(
        "CREATE_PLAN",
        ["strategy_analysis", "presentation_design"],
        metadata={"requires_llm_plan": True},
    ) is True
    assert should_invoke_llm_planner(
        "EXECUTE", ["strategy_analysis", "presentation_design"]
    ) is False
    assert should_plan("EXECUTE") is False
    assert should_plan("CREATE_PLAN") is True


def test_single_step_plan_skips_orchestration() -> None:
    plan = build_direct_execution_plan(
        goal="SWOT",
        summary="one skill",
        required_capabilities=["strategy_analysis"],
    )
    assert plan_requires_orchestration(plan) is False

    multi = build_direct_execution_plan(
        goal="pack",
        summary="multi",
        required_capabilities=["strategy_analysis", "presentation_design"],
    )
    assert plan_requires_orchestration(multi) is True


@pytest.mark.asyncio
async def test_create_plan_with_one_capability_does_not_call_llm_planner(settings: Settings) -> None:
    registry = create_capability_registry(settings)
    gateway, provider = _mock_gateway(settings, _plan_json())
    node = PlannerNode(TaskPlanner(gateway), registry)

    state = create_initial_state(execution_id="e1", trace_id="t1", user_input="Сделай SWOT")
    state["decision"] = {"action": "CREATE_PLAN"}
    state["understanding"] = {
        "goal": "SWOT",
        "summary": "single capability wrongly marked as plan",
        "required_capabilities": ["strategy_analysis"],
        "missing_information": [],
        "next_action": "create_plan",
    }

    update = await node(state)

    assert update["status"] == "direct_plan_ready"
    assert len(update["task_plan"]["steps"]) == 1
    assert provider.calls == []


@pytest.mark.asyncio
async def test_create_plan_linear_caps_uses_direct_plan_without_llm(settings: Settings) -> None:
    registry = create_capability_registry(settings)
    gateway, provider = _mock_gateway(settings, _plan_json())
    node = PlannerNode(TaskPlanner(gateway), registry)

    state = create_initial_state(execution_id="e1", trace_id="t1", user_input="Strategy and deck")
    state["decision"] = {"action": "CREATE_PLAN"}
    state["understanding"] = {
        "goal": "pack",
        "summary": "linear multi-skill",
        "required_capabilities": ["strategy_analysis", "presentation_design"],
        "missing_information": [],
        "next_action": "create_plan",
    }

    update = await node(state)

    assert update["status"] == "direct_plan_ready"
    # Resolver auto-completes presentation_design → document_rendering.
    caps = [step["capability"] for step in update["task_plan"]["steps"]]
    assert caps == ["strategy_analysis", "presentation_design", "document_rendering"]
    assert provider.calls == []


@pytest.mark.asyncio
async def test_create_plan_with_requires_llm_plan_calls_planner(settings: Settings) -> None:
    registry = create_capability_registry(settings)
    gateway, provider = _mock_gateway(
        settings,
        _plan_json(
            goal="Branching work",
            steps=[
                {"description": "Strategy", "capability": "strategy_analysis", "dependencies": []},
                {"description": "Deck", "capability": "presentation_design", "dependencies": [0]},
                {"description": "Render", "capability": "document_rendering", "dependencies": [1]},
            ],
        ),
    )
    node = PlannerNode(TaskPlanner(gateway), registry)

    state = create_initial_state(execution_id="e1", trace_id="t1", user_input="complex")
    state["decision"] = {"action": "CREATE_PLAN"}
    state["metadata"] = {"requires_llm_plan": True}
    state["understanding"] = {
        "goal": "Branching work",
        "summary": "needs planner",
        "required_capabilities": ["strategy_analysis", "presentation_design", "document_rendering"],
        "missing_information": [],
        "next_action": "create_plan",
    }

    update = await node(state)

    assert update["status"] == "planned"
    assert len(update["task_plan"]["steps"]) == 3
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_orchestration_skips_for_single_step_plan(settings: Settings) -> None:
    node = OrchestrationNode()
    plan = build_direct_execution_plan(
        goal="doc",
        summary="one",
        required_capabilities=["document_generation"],
    )
    state = create_initial_state(execution_id="e1", trace_id="t1", user_input="doc")
    state["task_plan"] = plan.model_dump(mode="json")
    state["decision"] = {"action": "EXECUTE"}

    update = await node(state)

    assert update["status"] == "orchestration_skipped"
    assert update["execution_graph"] is None


@pytest.mark.asyncio
async def test_execute_single_skill_avoids_graph_and_llm_planner(settings: Settings) -> None:
    registry = create_capability_registry(settings)
    gateway, provider = _mock_gateway(
        settings,
        _executive_json(
            goal="анализ",
            summary="single skill",
            action="EXECUTE",
            required_capabilities=["document_analysis"],
            next_action="execute",
        ),
    )
    runtime = AgentRuntime(
        graph=build_executive_graph(gateway, capability_registry=registry),
        checkpoint_manager=InMemoryCheckpointManager(),
    )

    result = await runtime.execute("Проанализируй отчёт")

    assert result["decision"]["action"] == "EXECUTE"
    assert result["task_plan"] is not None
    assert len(result["task_plan"]["steps"]) == 1
    assert result["execution_graph"] is None
    # Missing extracted_content → skill status=failed, no silent COMPLETED.
    assert result["task_execution"]["status"] == "FAILED"
    assert result["progress"] < 100.0
    assert len(provider.calls) == 1  # executive only


@pytest.mark.asyncio
async def test_create_plan_multi_capability_builds_graph_without_llm_planner(
    settings: Settings,
) -> None:
    """CREATE_PLAN with known linear caps → direct plan + graph; no LLM TaskPlanner."""
    from app.skills.base.skill import BaseSkill
    from app.skills.models import Capability, SkillMetadata
    from app.skills.registry import CapabilityRegistry

    class _OkSkill(BaseSkill):
        def __init__(self, skill_id: str, capability: str) -> None:
            super().__init__(
                metadata=SkillMetadata(
                    id=skill_id,
                    name=skill_id,
                    description="ok",
                    capabilities=[capability],
                    enabled=True,
                ),
                capabilities=[Capability(name=capability, description="ok", category="test")],
            )

        async def execute(self, payload: dict) -> dict:
            return {"status": "completed", "skill": self.name()}

    registry = CapabilityRegistry(settings)
    registry.register(_OkSkill("document_skill", "document_generation"))
    registry.register(_OkSkill("document_analysis_skill", "document_analysis"))
    registry.register(_OkSkill("analysis_skill", "data_analysis"))

    gateway, provider = _mock_gateway(
        settings,
        _executive_json(
            goal="Doc then analysis then data",
            summary="multi-stage",
            action="CREATE_PLAN",
            required_capabilities=["document_generation", "document_analysis", "data_analysis"],
            next_action="create_plan",
        ),
        _review_json(),
    )
    runtime = AgentRuntime(
        graph=build_executive_graph(gateway, capability_registry=registry),
        checkpoint_manager=InMemoryCheckpointManager(),
    )

    result = await runtime.execute(
        "Подготовь документ, анализ и данные",
        metadata={"auto_approve": True},
    )

    assert result["task_plan"] is not None
    assert len(result["task_plan"]["steps"]) == 3
    assert result["execution_graph"] is not None
    # executive + review only — no LLM TaskPlanner for linear known caps
    assert len(provider.calls) == 2
