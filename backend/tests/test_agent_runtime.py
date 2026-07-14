import pytest

from app.agent_runtime.checkpoint.manager import (
    InMemoryCheckpointManager,
    RedisCheckpointManager,
    create_checkpoint_manager,
)
from app.agent_runtime.checkpoint.redis_saver import RedisCheckpointSaver
from app.agent_runtime.exceptions import CheckpointError
from app.agent_runtime.exceptions import GraphBuildError, GraphExecutionError
from app.agent_runtime.graph.builder import GraphBuilder
from app.agent_runtime.graph.edges import FINISH_NODE, PROCESS_INPUT_NODE, wire_default_workflow
from app.agent_runtime.graph.nodes import FinishNode, InputNode
from app.agent_runtime.runtime import AgentRuntime, build_default_graph
from app.agent_runtime.state.models import create_initial_state
from app.core.config import Settings


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


@pytest.mark.asyncio
async def test_executive_graph_omits_dead_document_nodes() -> None:
    from app.agent_runtime.runtime import build_executive_graph
    from tests.llm_fixtures import executive_json, mock_gateway

    gateway, _ = mock_gateway(
        Settings(),
        executive_json(goal="g", summary="s", action="RESPOND", response_message="hi"),
    )
    graph = build_executive_graph(gateway)
    nodes = set(graph.get_graph().nodes)
    assert "document_creation" not in nodes
    assert "document_render" not in nodes
    assert "skill_resolver" in nodes
    assert "executor" in nodes


def test_build_default_graph_with_checkpoint_manager() -> None:
    manager = InMemoryCheckpointManager()
    graph = build_default_graph(checkpoint_manager=manager)
    assert graph is not None
    assert manager.get_checkpointer() is not None


class _FakeRedis:
    """Minimal sync Redis stub for app-level + LangGraph checkpointer tests."""

    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}
        self._sets: dict[str, set[str]] = {}

    def ping(self) -> bool:
        return True

    def set(self, key, value, ex=None) -> None:
        self._data[str(key)] = value if isinstance(value, bytes) else bytes(value)

    def get(self, key):
        return self._data.get(str(key))

    def delete(self, *keys) -> int:
        removed = 0
        for key in keys:
            k = str(key)
            if self._data.pop(k, None) is not None:
                removed += 1
            if self._sets.pop(k, None) is not None:
                removed += 1
        return removed

    def sadd(self, key, *members) -> int:
        bucket = self._sets.setdefault(str(key), set())
        before = len(bucket)
        bucket.update(str(m) for m in members)
        return len(bucket) - before

    def smembers(self, key):
        return set(self._sets.get(str(key), set()))

    def expire(self, key, _seconds) -> bool:
        return str(key) in self._data or str(key) in self._sets

    def scan_iter(self, match: str = "*", count: int = 10):
        prefix = match.rstrip("*")
        for key in list(self._data.keys()) + list(self._sets.keys()):
            if key.startswith(prefix):
                yield key


def test_redis_checkpoint_manager_roundtrip() -> None:
    client = _FakeRedis()
    manager = RedisCheckpointManager("redis://unused", ttl_seconds=60, client=client)
    state = create_initial_state(
        execution_id="exec-r1",
        trace_id="trace-r1",
        user_input="redis checkpoint",
    )
    state["status"] = "completed"
    manager.save("exec-r1", state)
    loaded = manager.load("exec-r1")
    assert loaded is not None
    assert loaded["user_input"] == "redis checkpoint"
    assert manager.delete("exec-r1") is True
    assert manager.load("exec-r1") is None
    assert isinstance(manager.get_checkpointer(), RedisCheckpointSaver)


def test_redis_langgraph_checkpointer_roundtrip() -> None:
    client = _FakeRedis()
    saver = RedisCheckpointSaver(client, ttl_seconds=60)
    config = {"configurable": {"thread_id": "t1", "checkpoint_ns": ""}}
    checkpoint = {
        "v": 1,
        "id": "1ef4f797-8335-6428-8001-8a1503f9b875",
        "ts": "2026-07-13T00:00:00+00:00",
        "channel_values": {"messages": ["hi"]},
        "channel_versions": {"messages": "00000000000000000000000000000001.1"},
        "versions_seen": {},
    }
    saved = saver.put(config, checkpoint, {"source": "test"}, {"messages": "00000000000000000000000000000001.1"})
    loaded = saver.get_tuple(saved)
    assert loaded is not None
    assert loaded.checkpoint["channel_values"]["messages"] == ["hi"]
    saver.put_writes(saved, [("messages", "pending")], task_id="task-1")
    again = saver.get_tuple(saved)
    assert again is not None
    assert again.pending_writes
    assert ("task-1", "messages", "pending") in again.pending_writes
    saver.delete_thread("t1")
    assert saver.get_tuple(saved) is None


def test_redis_checkpoint_manager_raises_when_redis_unavailable() -> None:
    class BoomRedis:
        def ping(self):
            raise ConnectionError("down")

    with pytest.raises(CheckpointError):
        RedisCheckpointManager("redis://unused", client=BoomRedis())  # type: ignore[arg-type]


def test_create_checkpoint_manager_defaults_to_memory_without_redis() -> None:
    manager = create_checkpoint_manager(Settings(app_env="development", redis_url=""))
    assert isinstance(manager, InMemoryCheckpointManager)


def test_create_checkpoint_manager_uses_redis_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeRedis()
    monkeypatch.setattr(
        "app.agent_runtime.checkpoint.manager.redis.from_url",
        lambda *_args, **_kwargs: fake,
    )
    # Independent of APP_ENV — any env with redis_url uses Redis.
    manager = create_checkpoint_manager(
        Settings(app_env="development", redis_url="redis://localhost:6379/15")
    )
    assert isinstance(manager, RedisCheckpointManager)
    assert isinstance(manager.get_checkpointer(), RedisCheckpointSaver)
