import json
from uuid import uuid4

import pytest

from app.agent_runtime.checkpoint.manager import InMemoryCheckpointManager
from app.agent_runtime.runtime import AgentRuntime, build_executive_graph
from app.agent_runtime.state.models import create_initial_state
from app.agents.executive.models import AgentUnderstanding
from app.core.config import Settings
from app.planning.executor import TaskExecutor
from app.planning.models import (
    ApprovalStatus,
    PlanStep,
    PlanStatus,
    StepStatus,
    TaskExecutionStatus,
    TaskPlan,
)
from app.quality.gate import QualityGate
from app.quality.nodes.quality_gate_node import QualityGateNode
from app.quality.reviewer import ReviewerAgent
from app.planning.nodes.executor_node import ExecutorNode
from app.planning.nodes.planner_node import PlannerNode
from app.planning.parsers.plan_parser import parse_task_plan
from app.planning.planner import TaskPlanner
from app.planning.policies.execution_policy import requires_approval, should_plan, should_retry_step
from app.skills.models import Capability
from app.skills.registry import create_capability_registry
from tests.llm_fixtures import creation_ast_json as _creation_ast_json
from tests.llm_fixtures import executive_json as _executive_json
from tests.llm_fixtures import mock_gateway as _mock_gateway
from tests.llm_fixtures import plan_json as _plan_json
from tests.llm_fixtures import review_json as _review_json


@pytest.fixture
def settings() -> Settings:
    return Settings(skills_enabled=True)


def test_parse_task_plan_with_dependencies() -> None:
    plan = parse_task_plan(_plan_json())
    assert plan.goal == "test goal"
    assert len(plan.steps) == 2
    assert plan.steps[1].dependencies == [plan.steps[0].id]


def test_should_plan_policy() -> None:
    assert should_plan("CREATE_PLAN") is True
    assert should_plan("EXECUTE") is True
    assert should_plan("RESPOND") is False


def test_requires_approval_policy() -> None:
    assert requires_approval("CREATE_PLAN") is True
    assert requires_approval("RESPOND") is False


def test_retry_policy() -> None:
    step = PlanStep(description="test", capability="document_analysis", status=StepStatus.FAILED)
    assert should_retry_step(step, 1) is True
    assert should_retry_step(step, 3) is False


@pytest.mark.asyncio
async def test_task_planner_creates_plan(settings: Settings) -> None:
    gateway, _ = _mock_gateway(settings, _plan_json(goal="Подготовить КП"))
    planner = TaskPlanner(gateway)
    understanding = AgentUnderstanding(
        goal="Подготовить КП для клиента",
        summary="Нужно коммерческое предложение",
        required_capabilities=["document_generation"],
        missing_information=["данные клиента"],
        next_action="create_plan",
    )

    plan = await planner.create_plan(
        understanding=understanding,
        execution_context={"user_input": "Подготовь КП"},
        available_capabilities=[
            Capability(name="document_generation", description="Создание документов", category="document"),
            Capability(name="document_analysis", description="Анализ документов", category="document"),
        ],
    )

    assert plan.status == PlanStatus.READY
    assert len(plan.steps) == 2
    assert plan.steps[0].capability == "document_analysis"


@pytest.mark.asyncio
async def test_task_executor_runs_steps(settings: Settings) -> None:
    registry = create_capability_registry(settings)
    plan = parse_task_plan(_plan_json(goal="Execute test"))
    executor = TaskExecutor()

    execution = await executor.execute(plan, registry)

    assert execution.status == TaskExecutionStatus.COMPLETED
    assert all(step.status == StepStatus.COMPLETED for step in plan.steps)
    assert execution.results["steps_completed"] == 2


@pytest.mark.asyncio
async def test_task_executor_handles_missing_capability(settings: Settings) -> None:
    registry = create_capability_registry(settings)
    plan = TaskPlan(
        goal="fail test",
        summary="missing capability",
        steps=[
            PlanStep(description="Unknown step", capability="nonexistent_capability"),
        ],
    )
    executor = TaskExecutor()

    execution = await executor.execute(plan, registry)

    assert execution.status == TaskExecutionStatus.FAILED
    assert plan.steps[0].status == StepStatus.FAILED


@pytest.mark.asyncio
async def test_executor_node_waiting_approval(settings: Settings) -> None:
    registry = create_capability_registry(settings)
    node = ExecutorNode(TaskExecutor(), registry)
    plan = parse_task_plan(_plan_json())

    state = create_initial_state(
        execution_id="exec-1",
        trace_id="trace-1",
        user_input="Подготовь КП",
    )
    state["task_plan"] = plan.model_dump(mode="json")
    state["decision"] = {"action": "CREATE_PLAN"}

    update = await node(state)

    assert update["status"] == "waiting_approval"
    assert update["task_execution"]["status"] == TaskExecutionStatus.WAITING_APPROVAL.value
    assert update["task_execution"]["approval"]["status"] == ApprovalStatus.PENDING_APPROVAL.value


@pytest.mark.asyncio
async def test_executor_node_with_auto_approve(settings: Settings) -> None:
    registry = create_capability_registry(settings)
    node = ExecutorNode(TaskExecutor(), registry)
    plan = parse_task_plan(_plan_json())

    state = create_initial_state(
        execution_id="exec-1",
        trace_id="trace-1",
        user_input="Подготовь КП",
    )
    state["task_plan"] = plan.model_dump(mode="json")
    state["decision"] = {"action": "EXECUTE"}
    state["metadata"] = {"auto_approve": True}

    update = await node(state)

    assert update["status"] == "executed"
    assert update["task_execution"]["status"] == TaskExecutionStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_planner_node_skips_for_respond(settings: Settings) -> None:
    registry = create_capability_registry(settings)
    gateway, _ = _mock_gateway(settings, _plan_json())
    node = PlannerNode(TaskPlanner(gateway), registry)

    state = create_initial_state(
        execution_id="exec-1",
        trace_id="trace-1",
        user_input="Привет",
    )
    state["decision"] = {"action": "RESPOND"}
    state["understanding"] = {
        "goal": "greet",
        "summary": "greeting",
        "required_capabilities": [],
        "missing_information": [],
        "next_action": "respond",
    }

    update = await node(state)
    assert update["status"] == "planning_skipped"
    assert update["task_plan"] is None


@pytest.mark.asyncio
async def test_quality_gate_node(settings: Settings) -> None:
    gateway, _ = _mock_gateway(settings, _review_json())
    node = QualityGateNode(QualityGate(ReviewerAgent(gateway)))
    state = create_initial_state(
        execution_id="exec-1",
        trace_id="trace-1",
        user_input="test",
    )
    state["decision"] = {"action": "EXECUTE"}
    state["understanding"] = {"goal": "test document"}
    state["document_ast"] = {
        "root": {
            "node_type": "document",
            "children": [
                {
                    "node_type": "section",
                    "children": [{"node_type": "heading", "content": "Title", "children": []}],
                }
            ],
        },
        "node_count": 3,
    }
    state["render_result"] = {"metadata": {"format": "docx"}, "status": "COMPLETED"}

    update = await node(state)
    assert update["quality_check"]["passed"] is True
    assert update["review_result"]["status"] == "PASS"
    assert update["result"]["review_result"]["status"] == "PASS"


@pytest.mark.asyncio
async def test_langgraph_planning_integration(settings: Settings) -> None:
    registry = create_capability_registry(settings)
    gateway, _ = _mock_gateway(
        settings,
        _executive_json(
            goal="Подготовить КП",
            summary="Коммерческое предложение",
            action="EXECUTE",
            required_capabilities=["document_generation", "document_analysis"],
            next_action="execute",
        ),
        _plan_json(goal="Подготовить КП для клиента"),
        _creation_ast_json(title="Коммерческое предложение"),
        _review_json(summary="Document structure and output meet the goal"),
    )
    runtime = AgentRuntime(
        graph=build_executive_graph(gateway, capability_registry=registry),
        checkpoint_manager=InMemoryCheckpointManager(),
    )

    result = await runtime.execute(
        "Подготовь КП для клиента",
        metadata={"auto_approve": True},
    )

    assert result["task_plan"] is not None
    assert len(result["task_plan"]["steps"]) == 2
    assert result["document_ast"] is not None
    assert result["document_creation_result"]["missing_information"] == []
    assert result["quality_check"]["passed"] is True
    assert result["review_result"]["status"] == "PASS"
    assert result["result"]["task_plan"]["goal"] == "Подготовить КП для клиента"
