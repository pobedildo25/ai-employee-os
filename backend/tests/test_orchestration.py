from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_orchestrator
from app.main import create_app
from app.orchestration.dependency_resolver import DependencyResolver
from app.orchestration.execution_graph import build_execution_graph
from app.orchestration.models import (
    ExecutionControlStatus,
    ExecutionGraph,
    ExecutionGraphNode,
    ExecutionState,
    NodeStatus,
)
from app.orchestration.orchestrator import Orchestrator
from app.orchestration.progress_tracker import ProgressTracker
from app.orchestration.scheduler import Scheduler
from app.orchestration.state_manager import StateManager
from app.orchestration.store import ExecutionStore
from app.orchestration.validators.execution_validator import ExecutionValidationError, ExecutionValidator
from app.planning.models import PlanStep, StepStatus, TaskExecutionStatus, TaskPlan
from app.planning.parsers.plan_parser import parse_task_plan
from app.skills.registry import create_capability_registry
from app.core.config import Settings
from tests.llm_fixtures import plan_json


@pytest.fixture
def settings() -> Settings:
    return Settings(skills_enabled=True)


@pytest.fixture
def sample_plan() -> TaskPlan:
    return parse_task_plan(plan_json(goal="Исследование рынка"))


@pytest.fixture
def parallel_plan() -> TaskPlan:
    return TaskPlan(
        goal="Parallel test",
        summary="Independent steps",
        steps=[
            PlanStep(description="Исследование рынка", capability="document_analysis"),
            PlanStep(description="Стратегия", capability="document_generation"),
            PlanStep(
                description="Презентация",
                capability="document_generation",
                dependencies=[],
            ),
        ],
    )


@pytest.fixture
def orchestrator() -> Orchestrator:
    store = ExecutionStore()
    return Orchestrator(store=store)


def test_build_execution_graph(sample_plan: TaskPlan) -> None:
    graph = build_execution_graph(sample_plan)
    assert graph.plan_id == sample_plan.id
    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1
    assert len(graph.execution_order) == 2
    node_ids = list(graph.nodes.keys())
    assert graph.nodes[node_ids[1]].dependencies == [sample_plan.steps[0].id]


def test_execution_graph_validation_cycle() -> None:
    a_id = uuid4()
    b_id = uuid4()
    graph = ExecutionGraph(
        plan_id=uuid4(),
        nodes={
            str(a_id): ExecutionGraphNode(
                id=a_id,
                capability="a",
                description="A",
                dependencies=[b_id],
            ),
            str(b_id): ExecutionGraphNode(
                id=b_id,
                capability="b",
                description="B",
                dependencies=[a_id],
            ),
        },
    )
    with pytest.raises(ExecutionValidationError, match="cycle"):
        ExecutionValidator().validate_graph(graph)


def test_dependency_resolver_ready_and_waiting(sample_plan: TaskPlan) -> None:
    graph = build_execution_graph(sample_plan)
    resolver = DependencyResolver()
    ready, waiting = resolver.resolve(graph)
    assert len(ready) == 1
    assert ready[0].capability == "document_analysis"
    assert len(waiting) == 1
    assert waiting[0].capability == "document_generation"


def test_scheduler_tracks_statuses(sample_plan: TaskPlan) -> None:
    graph = build_execution_graph(sample_plan)
    scheduler = Scheduler()
    resolver = DependencyResolver()
    ready, _ = resolver.resolve(graph)
    running = scheduler.mark_running(graph, ready)
    assert running
    assert graph.nodes[running[0]].status == NodeStatus.RUNNING
    scheduler.mark_completed(graph, running[0], {"ok": True})
    assert graph.nodes[running[0]].status == NodeStatus.COMPLETED


def test_progress_tracker_percent(sample_plan: TaskPlan) -> None:
    graph = build_execution_graph(sample_plan)
    tracker = ProgressTracker()
    assert tracker.calculate_progress(graph) == 0.0
    node_id = graph.execution_order[0]
    graph.nodes[node_id].status = NodeStatus.COMPLETED
    assert tracker.calculate_progress(graph) == 50.0


def test_telegram_progress_message(sample_plan: TaskPlan) -> None:
    graph = build_execution_graph(sample_plan)
    tracker = ProgressTracker()
    graph.nodes[graph.execution_order[0]].status = NodeStatus.COMPLETED
    graph.nodes[graph.execution_order[1]].status = NodeStatus.RUNNING
    message = tracker.build_telegram_progress("exec-1", graph)
    assert message.progress_percent == 50
    assert len(message.lines) == 2
    assert message.lines[0].status_icon == "✅"
    assert message.lines[0].status_label == "выполнено"
    assert message.lines[1].status_icon == "⏳"
    text = tracker.format_telegram_text(message)
    assert "Исследование" in text or "Analyze" in text


def test_state_manager_tracks_nodes(sample_plan: TaskPlan) -> None:
    graph = build_execution_graph(sample_plan)
    manager = StateManager()
    state = manager.create_state("exec-1", graph)
    graph.nodes[graph.execution_order[0]].status = NodeStatus.COMPLETED
    refreshed = manager.refresh(state, graph)
    assert refreshed.completed_nodes == [graph.execution_order[0]]


@pytest.mark.asyncio
async def test_orchestrator_executes_graph(settings: Settings, sample_plan: TaskPlan, orchestrator: Orchestrator) -> None:
    registry = create_capability_registry(settings)
    graph = build_execution_graph(sample_plan)
    state = StateManager().create_state("exec-orch-1", graph)

    final_state, execution = await orchestrator.execute(
        graph,
        sample_plan,
        registry,
        state,
        execution_context={"user_input": "test"},
        trace_id="trace-1",
    )

    assert execution.status == TaskExecutionStatus.COMPLETED
    assert final_state.progress == 100.0
    assert len(final_state.completed_nodes) == 2


@pytest.mark.asyncio
async def test_orchestrator_retry_on_missing_capability(settings: Settings, orchestrator: Orchestrator) -> None:
    registry = create_capability_registry(settings)
    plan = TaskPlan(
        goal="fail",
        summary="missing",
        steps=[PlanStep(description="bad", capability="nonexistent_capability")],
    )
    graph = build_execution_graph(plan)
    state = StateManager().create_state("exec-fail", graph)

    final_state, execution = await orchestrator.execute(
        graph,
        plan,
        registry,
        state,
        trace_id="trace-fail",
    )

    assert execution.status == TaskExecutionStatus.FAILED
    assert final_state.failed_nodes
    assert plan.steps[0].status == StepStatus.FAILED


def test_pause_resume_cancel(sample_plan: TaskPlan, orchestrator: Orchestrator) -> None:
    graph = build_execution_graph(sample_plan)
    state = StateManager().create_state("exec-control", graph)
    state.control_status = ExecutionControlStatus.RUNNING

    from app.orchestration.models import ExecutionRecord
    from app.planning.models import TaskExecution

    orchestrator._store.save(
        ExecutionRecord(
            execution_id="exec-control",
            trace_id="t",
            graph=graph,
            state=state,
            task_plan=sample_plan.model_dump(mode="json"),
            task_execution=TaskExecution(plan_id=sample_plan.id).model_dump(mode="json"),
            telegram_progress=ProgressTracker().build_telegram_progress("exec-control", graph),
        )
    )

    paused = orchestrator.pause_execution("exec-control")
    assert paused is not None
    assert paused.control_status == ExecutionControlStatus.PAUSED

    resumed = orchestrator.resume_execution("exec-control")
    assert resumed is not None
    assert resumed.control_status == ExecutionControlStatus.RUNNING

    cancelled = orchestrator.cancel_execution("exec-control")
    assert cancelled is not None
    assert cancelled.control_status == ExecutionControlStatus.CANCELLED


@pytest.mark.asyncio
async def test_orchestration_node_builds_graph(settings: Settings) -> None:
    from app.agent_runtime.state.models import create_initial_state
    from app.orchestration.nodes.orchestration_node import OrchestrationNode

    node = OrchestrationNode()
    plan = parse_task_plan(plan_json())
    state = create_initial_state(execution_id="exec-node", trace_id="trace-node", user_input="test")
    state["decision"] = {"action": "EXECUTE"}
    state["task_plan"] = plan.model_dump(mode="json")

    update = await node(state)
    assert update["status"] == "orchestrated"
    assert update["execution_graph"] is not None
    assert update["execution_state"] is not None
    assert update["progress"] == 0.0
    assert update["telegram_progress"] is not None


@pytest.mark.asyncio
async def test_executions_api(orchestrator: Orchestrator, sample_plan: TaskPlan) -> None:
    graph = build_execution_graph(sample_plan)
    state = ExecutionState(execution_id="api-exec-1", graph_id=graph.id, progress=50.0)
    from app.orchestration.models import ExecutionRecord

    orchestrator._store.save(
        ExecutionRecord(
            execution_id="api-exec-1",
            trace_id="api-trace",
            graph=graph,
            state=state,
            task_plan=sample_plan.model_dump(mode="json"),
            telegram_progress=ProgressTracker().build_telegram_progress("api-exec-1", graph, progress=50.0),
        )
    )

    from app.api.deps import get_orchestrator

    app = create_app()

    def override_orchestrator():
        return orchestrator

    app.dependency_overrides[get_orchestrator] = override_orchestrator

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        detail = await client.get("/api/v1/executions/api-exec-1")
        assert detail.status_code == 200
        body = detail.json()
        assert body["execution_id"] == "api-exec-1"
        assert body["progress"] == 50.0

        progress = await client.get("/api/v1/executions/api-exec-1/progress")
        assert progress.status_code == 200
        assert progress.json()["progress_percent"] == 50

        state.control_status = ExecutionControlStatus.RUNNING
        orchestrator._store.update_state("api-exec-1", state)

        pause = await client.post("/api/v1/executions/api-exec-1/pause")
        assert pause.status_code == 200
        assert pause.json()["status"] == ExecutionControlStatus.PAUSED.value

        resume = await client.post("/api/v1/executions/api-exec-1/resume")
        assert resume.status_code == 200
        assert resume.json()["status"] == ExecutionControlStatus.RUNNING.value

        cancel = await client.post("/api/v1/executions/api-exec-1/cancel")
        assert cancel.status_code == 200
        assert cancel.json()["status"] == ExecutionControlStatus.CANCELLED.value

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_langgraph_orchestration_integration(settings: Settings) -> None:
    from app.agent_runtime.checkpoint.manager import InMemoryCheckpointManager
    from app.agent_runtime.runtime import AgentRuntime, build_executive_graph
    from tests.llm_fixtures import executive_json, mock_gateway, review_json

    registry = create_capability_registry(settings)
    gateway, _ = mock_gateway(
        settings,
        executive_json(
            goal="Подготовить КП",
            summary="Коммерческое предложение",
            action="EXECUTE",
            required_capabilities=["document_generation", "document_analysis"],
            next_action="execute",
        ),
        plan_json(goal="Подготовить КП для клиента"),
        review_json(summary="Plan execution meets the goal"),
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
    assert result["execution_graph"] is not None
    assert result["execution_state"] is not None
    assert result["progress"] == 100.0
    assert result["telegram_progress"] is not None
    assert result["quality_check"]["passed"] is True
    assert result["result"]["task_plan"]["goal"] == "Подготовить КП для клиента"
