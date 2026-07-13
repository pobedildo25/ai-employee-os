import pytest

from app.agent_runtime.checkpoint.manager import InMemoryCheckpointManager
from app.agent_runtime.exceptions import GraphBuildError, GraphExecutionError
from app.agent_runtime.graph.builder import GraphBuilder
from app.agent_runtime.graph.edges import FINISH_NODE, PROCESS_INPUT_NODE, wire_default_workflow
from app.agent_runtime.graph.nodes import FinishNode, InputNode
from app.agent_runtime.runtime import AgentRuntime, build_default_graph
from app.agent_runtime.state.models import create_initial_state


def _demo_runtime() -> AgentRuntime:
    return AgentRuntime(
        graph=build_default_graph(),
        checkpoint_manager=InMemoryCheckpointManager(),
    )


def test_graph_builder_creates_default_workflow() -> None:
    builder = GraphBuilder()
    builder.add_node(InputNode())
    builder.add_node(FinishNode())
    wire_default_workflow(builder)

    graph = builder.build()
    assert graph is not None


def test_graph_builder_requires_nodes() -> None:
    builder = GraphBuilder()
    with pytest.raises(GraphBuildError, match="without nodes"):
        builder.build()


def test_graph_builder_requires_edges() -> None:
    builder = GraphBuilder()
    builder.add_node(InputNode())
    with pytest.raises(GraphBuildError, match="without edges"):
        builder.build()


def test_graph_builder_rejects_duplicate_nodes() -> None:
    builder = GraphBuilder()
    builder.add_node(InputNode())
    with pytest.raises(GraphBuildError, match="already registered"):
        builder.add_node(InputNode())


@pytest.mark.asyncio
async def test_runtime_execute_workflow() -> None:
    runtime = _demo_runtime()
    result = await runtime.execute("hello world", trace_id="trace-abc")

    assert result["status"] == "completed"
    assert result["trace_id"] == "trace-abc"
    assert result["current_step"] == FINISH_NODE
    assert result["result"]["processed"] is True
    assert result["messages"] == [{"role": "user", "content": "hello world"}]


@pytest.mark.asyncio
async def test_runtime_execute_updates_state() -> None:
    runtime = _demo_runtime()
    result = await runtime.execute(
        "test input",
        context={"project_id": "p-1"},
        metadata={"source": "test"},
    )

    assert result["user_input"] == "test input"
    assert result["context"] == {"project_id": "p-1"}
    assert result["metadata"] == {"source": "test"}
    assert result["execution_id"]


@pytest.mark.asyncio
async def test_runtime_stream_workflow() -> None:
    runtime = _demo_runtime()
    events: list[dict] = []

    async for event in runtime.stream("stream me", trace_id="trace-stream"):
        events.append(event)

    assert len(events) == 3
    assert "_bootstrap" in events[0]
    assert events[0]["_bootstrap"]["trace_id"] == "trace-stream"
    assert PROCESS_INPUT_NODE in events[1]
    assert FINISH_NODE in events[2]
    assert events[1][PROCESS_INPUT_NODE]["status"] == "processing"
    assert events[2][FINISH_NODE]["status"] == "completed"


def test_checkpoint_save_and_load() -> None:
    manager = InMemoryCheckpointManager()
    state = create_initial_state(
        execution_id="exec-1",
        trace_id="trace-1",
        user_input="checkpoint test",
    )
    state["status"] = "completed"

    manager.save("exec-1", state)
    loaded = manager.load("exec-1")

    assert loaded is not None
    assert loaded["execution_id"] == "exec-1"
    assert loaded["user_input"] == "checkpoint test"
    assert loaded["status"] == "completed"


def test_checkpoint_delete() -> None:
    manager = InMemoryCheckpointManager()
    state = create_initial_state(
        execution_id="exec-2",
        trace_id="trace-2",
        user_input="delete me",
    )

    manager.save("exec-2", state)
    assert manager.delete("exec-2") is True
    assert manager.load("exec-2") is None
    assert manager.delete("exec-2") is False


@pytest.mark.asyncio
async def test_runtime_saves_checkpoint_after_execute() -> None:
    manager = InMemoryCheckpointManager()
    runtime = AgentRuntime(graph=build_default_graph(), checkpoint_manager=manager)
    result = await runtime.execute("persist this")

    stored = manager.load(result["execution_id"])
    assert stored is not None
    assert stored["status"] == "completed"
    assert stored["user_input"] == "persist this"


@pytest.mark.asyncio
async def test_runtime_handles_execution_error() -> None:
    class FailingNode(InputNode):
        name = "process_input"

        def __call__(self, state):
            raise RuntimeError("node failure")

    builder = GraphBuilder()
    builder.add_node(FailingNode())
    builder.add_node(FinishNode())
    wire_default_workflow(builder)

    runtime = AgentRuntime(graph=builder.build(), checkpoint_manager=InMemoryCheckpointManager())

    with pytest.raises(GraphExecutionError, match="Workflow execution failed"):
        await runtime.execute("fail")


def test_build_default_graph_with_checkpoint_manager() -> None:
    manager = InMemoryCheckpointManager()
    graph = build_default_graph(checkpoint_manager=manager)
    assert graph is not None
    assert manager.get_checkpointer() is not None
