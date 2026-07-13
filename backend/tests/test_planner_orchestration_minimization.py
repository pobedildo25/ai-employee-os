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
    capabilities_require_llm_planner,
    plan_requires_orchestration,
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


def test_llm_planner_requires_at_least_two_capabilities() -> None:
    assert capabilities_require_llm_planner([]) is False
    assert capabilities_require_llm_planner(["strategy_analysis"]) is False
    assert capabilities_require_llm_planner(["research", "strategy_analysis"]) is True
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
        required_capabilities=["research", "strategy_analysis"],
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
async def test_create_plan_multi_capability_builds_graph(settings: Settings) -> None:
    registry = create_capability_registry(settings)
    gateway, provider = _mock_gateway(
        settings,
        _executive_json(
            goal="Research then strategy then deck",
            summary="multi-stage",
            action="CREATE_PLAN",
            required_capabilities=["research", "strategy_analysis", "presentation_design"],
            next_action="create_plan",
        ),
        _plan_json(
            goal="Research then strategy then deck",
            steps=[
                {"description": "Research", "capability": "research", "dependencies": []},
                {"description": "Strategy", "capability": "strategy_analysis", "dependencies": [0]},
                {"description": "Deck", "capability": "presentation_design", "dependencies": [1]},
            ],
        ),
        _review_json(),
    )
    runtime = AgentRuntime(
        graph=build_executive_graph(gateway, capability_registry=registry),
        checkpoint_manager=InMemoryCheckpointManager(),
    )

    result = await runtime.execute(
        "Исследуй рынок, подготовь стратегию и презентацию",
        metadata={"auto_approve": True},
    )

    assert result["task_plan"] is not None
    assert len(result["task_plan"]["steps"]) == 3
    assert result["execution_graph"] is not None
    assert len(provider.calls) == 3  # executive + planner + review
