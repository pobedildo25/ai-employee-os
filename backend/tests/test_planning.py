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
from app.skills.base.skill import BaseSkill
from app.skills.models import Capability, SkillMetadata
from app.skills.registry import CapabilityRegistry, create_capability_registry
from tests.llm_fixtures import creation_ast_json as _creation_ast_json
from tests.llm_fixtures import executive_json as _executive_json
from tests.llm_fixtures import mock_gateway as _mock_gateway
from tests.llm_fixtures import plan_json as _plan_json
from tests.llm_fixtures import review_json as _review_json


class _OkSkill(BaseSkill):
    """Test double that reports successful skill completion."""

    def __init__(self, skill_id: str, capability: str) -> None:
        super().__init__(
            metadata=SkillMetadata(
                id=skill_id,
                name=skill_id,
                description="ok",
                capabilities=[capability],
                enabled=True,
            ),
            capabilities=[
                Capability(name=capability, description="ok", category="test"),
            ],
        )

    async def execute(self, payload: dict) -> dict:
        return {"status": "completed", "skill": self.name()}


def _ok_registry() -> CapabilityRegistry:
    registry = CapabilityRegistry(Settings(skills_enabled=True))
    registry.register(_OkSkill("document_analysis_skill", "document_analysis"))
    registry.register(_OkSkill("document_skill", "document_generation"))
    registry.register(_OkSkill("analysis_skill", "data_analysis"))
    registry.register(_OkSkill("file_skill", "file_processing"))
    return registry


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
    assert should_plan("EXECUTE") is False
    assert should_plan("RESPOND") is False
    assert should_plan("ASK_CLARIFICATION") is False


def test_requires_approval_policy() -> None:
    assert requires_approval("CREATE_PLAN") is True
    assert requires_approval("EXECUTE") is False
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
    registry = _ok_registry()
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


class _NoStatusSkill(BaseSkill):
    def __init__(self) -> None:
        super().__init__(
            metadata=SkillMetadata(
                id="no_status_skill",
                name="no_status_skill",
                description="missing status",
                capabilities=["document_analysis"],
                enabled=True,
            ),
            capabilities=[
                Capability(name="document_analysis", description="ok", category="test"),
            ],
        )

    async def execute(self, payload: dict) -> dict:
        return {"skill": self.name(), "payload_keys": list(payload.keys())}


@pytest.mark.asyncio
async def test_task_executor_fails_when_skill_dict_missing_status() -> None:
    registry = CapabilityRegistry(Settings(skills_enabled=True))
    registry.register(_NoStatusSkill())
    plan = TaskPlan(
        goal="fail missing status",
        summary="dict without status must fail",
        steps=[PlanStep(description="Analyze", capability="document_analysis")],
    )
    executor = TaskExecutor()

    execution = await executor.execute(plan, registry)

    assert execution.status == TaskExecutionStatus.FAILED
    assert plan.steps[0].status == StepStatus.FAILED


def test_skill_result_succeeded_missing_status_is_failure() -> None:
    from app.planning.executor import _skill_result_succeeded

    assert _skill_result_succeeded({"skill": "x"}) is False
    assert _skill_result_succeeded({"status": "completed"}) is True
    assert _skill_result_succeeded("ok") is True
    assert _skill_result_succeeded(None) is True


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
async def test_executor_node_execute_skips_approval(settings: Settings) -> None:
    registry = _ok_registry()
    node = ExecutorNode(TaskExecutor(), registry)
    plan = parse_task_plan(_plan_json())

    state = create_initial_state(
        execution_id="exec-1",
        trace_id="trace-1",
        user_input="Подготовь КП",
    )
    state["task_plan"] = plan.model_dump(mode="json")
    state["decision"] = {"action": "EXECUTE"}

    update = await node(state)

    assert update["status"] == "executed"
    assert update["task_execution"]["status"] == TaskExecutionStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_executor_node_with_auto_approve(settings: Settings) -> None:
    registry = _ok_registry()
    node = ExecutorNode(TaskExecutor(), registry)
    plan = parse_task_plan(_plan_json())

    state = create_initial_state(
        execution_id="exec-1",
        trace_id="trace-1",
        user_input="Подготовь КП",
    )
    state["task_plan"] = plan.model_dump(mode="json")
    state["decision"] = {"action": "CREATE_PLAN"}
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
async def test_planner_node_builds_direct_plan_for_execute(settings: Settings) -> None:
    registry = create_capability_registry(settings)
    gateway, provider = _mock_gateway(settings, _plan_json())
    node = PlannerNode(TaskPlanner(gateway), registry)

    state = create_initial_state(
        execution_id="exec-1",
        trace_id="trace-1",
        user_input="Создай SWOT-анализ",
    )
    state["decision"] = {"action": "EXECUTE"}
    state["understanding"] = {
        "goal": "создать SWOT-анализ",
        "summary": "Одноартефактная задача",
        "required_capabilities": ["strategy_analysis"],
        "missing_information": [],
        "next_action": "execute",
    }

    update = await node(state)

    assert update["status"] == "direct_plan_ready"
    assert update["task_plan"] is not None
    assert len(update["task_plan"]["steps"]) == 1
    assert update["task_plan"]["steps"][0]["capability"] == "strategy_analysis"
    assert provider.calls == []


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
async def test_langgraph_execute_uses_direct_plan_without_llm_planner(settings: Settings) -> None:
    registry = _ok_registry()
    gateway, provider = _mock_gateway(
        settings,
        _executive_json(
            goal="Подготовить КП",
            summary="Коммерческое предложение",
            action="EXECUTE",
            required_capabilities=["document_generation", "document_analysis"],
            next_action="execute",
        ),
        _review_json(summary="Plan execution meets the goal"),
    )
    runtime = AgentRuntime(
        graph=build_executive_graph(gateway, capability_registry=registry),
        checkpoint_manager=InMemoryCheckpointManager(),
    )

    result = await runtime.execute("Подготовь КП для клиента")

    assert result["task_plan"] is not None
    assert len(result["task_plan"]["steps"]) == 2
    assert {step["capability"] for step in result["task_plan"]["steps"]} == {
        "document_generation",
        "document_analysis",
    }
    assert result["execution_graph"] is not None
    assert result["execution_state"] is not None
    assert result["progress"] == 100.0
    assert result["quality_check"]["passed"] is True
    assert result["review_result"]["status"] == "PASS"
    assert result["result"]["task_plan"]["goal"] == "Подготовить КП"
    # Executive only — stub capabilities, non-document quality path.
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_langgraph_create_plan_linear_caps_skip_llm_planner(settings: Settings) -> None:
    registry = _ok_registry()
    gateway, provider = _mock_gateway(
        settings,
        _executive_json(
            goal="Подготовить документ и анализ",
            summary="Многоэтапная задача",
            action="CREATE_PLAN",
            required_capabilities=["document_generation", "document_analysis"],
            next_action="create_plan",
        ),
        _review_json(summary="Multi-step plan executed"),
    )
    runtime = AgentRuntime(
        graph=build_executive_graph(gateway, capability_registry=registry),
        checkpoint_manager=InMemoryCheckpointManager(),
    )

    result = await runtime.execute(
        "Подготовь документ и анализ",
        metadata={"auto_approve": True},
    )

    assert result["task_plan"] is not None
    assert len(result["task_plan"]["steps"]) == 2
    assert result["execution_graph"] is not None
    # executive + review — no LLM TaskPlanner for known linear caps
    assert len(provider.calls) == 2
