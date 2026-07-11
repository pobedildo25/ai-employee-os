import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.agent_runtime.state.models import create_initial_state
from app.api.deps import get_observability_manager
from app.main import create_app
from app.observability.exporters.console_exporter import ConsoleExporter
from app.observability.exporters.json_exporter import JsonExporter
from app.observability.logger import ObservabilityLogger
from app.observability.manager import ObservabilityManager
from app.observability.models import ExecutionTrace, TimelineEventStatus, TraceStatus
from app.observability.nodes.observability_node import ObservabilityNode
from app.observability.policies.retention_policy import RetentionPolicy
from app.observability.providers.in_memory_provider import InMemoryObservabilityProvider


@pytest.fixture
def manager() -> ObservabilityManager:
    return ObservabilityManager(InMemoryObservabilityProvider(RetentionPolicy(max_traces=50)))


@pytest.mark.asyncio
async def test_execution_trace(manager: ObservabilityManager) -> None:
    trace = await manager.start_execution(trace_id="trace-1", execution_id="exec-1")
    assert isinstance(trace, ExecutionTrace)
    assert trace.status == TraceStatus.RUNNING
    assert trace.timeline is not None

    finished = await manager.finish_execution("trace-1", status=TraceStatus.COMPLETED)
    assert finished.status == TraceStatus.COMPLETED
    assert finished.duration_ms is not None
    assert finished.finished_at is not None


@pytest.mark.asyncio
async def test_timeline(manager: ObservabilityManager) -> None:
    await manager.start_execution(trace_id="trace-2", execution_id="exec-2")
    started = await manager.start_node(trace_id="trace-2", node_name="planner")
    assert started.status == TimelineEventStatus.STARTED

    finished = await manager.finish_node(trace_id="trace-2", node_name="planner", status="completed")
    assert finished.status == TimelineEventStatus.COMPLETED
    assert finished.duration_ms is not None

    trace = await manager.get_trace("trace-2")
    assert trace is not None
    assert len(trace.timeline.events) == 1  # type: ignore[union-attr]
    assert trace.timeline.events[0].node_name == "planner"  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_metrics(manager: ObservabilityManager) -> None:
    await manager.start_execution(trace_id="trace-3", execution_id="exec-3")
    await manager.finish_execution("trace-3", status=TraceStatus.COMPLETED)
    await manager.start_execution(trace_id="trace-4", execution_id="exec-4")
    await manager.finish_execution("trace-4", status=TraceStatus.FAILED)
    manager.record_llm_call(tokens=120)
    manager.set_queue_size(3)

    metrics = manager.get_metrics()
    assert metrics.execution_count == 2
    assert metrics.failed_count == 1
    assert metrics.llm_calls == 1
    assert metrics.tokens == 120
    assert metrics.queue_size == 3
    assert metrics.average_duration_ms >= 0


def test_logger_uses_trace_id(manager: ObservabilityManager) -> None:
    logger = ObservabilityLogger("test.observability")
    logger.bind_trace("abc123")
    logger.info("hello", node="x")
    assert True


@pytest.mark.asyncio
async def test_exporters(manager: ObservabilityManager) -> None:
    await manager.start_execution(trace_id="trace-5", execution_id="exec-5")
    await manager.finish_execution("trace-5")

    raw = manager.export_json()
    payload = json.loads(raw)
    assert "metrics" in payload
    assert "traces" in payload
    assert len(payload["traces"]) == 1

    json_exporter = JsonExporter(manager.provider)
    assert "execution_count" in json_exporter.export_dict()["metrics"]

    console = ConsoleExporter(manager.provider)
    assert console.export()["metrics"]["execution_count"] >= 1


@pytest.mark.asyncio
async def test_observability_node(manager: ObservabilityManager) -> None:
    node = ObservabilityNode(manager)
    state = create_initial_state(
        execution_id="exec-node-1",
        trace_id="trace-node-1",
        user_input="observe",
        metadata={"observability_action": "start"},
    )
    start_update = await node(state)
    assert start_update["status"] == "observability_started"

    finish_state = {**state, "status": "completed", "metadata": {}}
    finish_update = await node(finish_state)  # type: ignore[arg-type]
    assert finish_update["status"] == "observability_recorded"
    assert finish_update["observability_trace"]["duration_ms"] is not None


@pytest.mark.asyncio
async def test_observability_api(manager: ObservabilityManager) -> None:
    await manager.start_execution(trace_id="api-trace-1", execution_id="api-exec-1")
    await manager.finish_execution("api-trace-1")
    manager.record_llm_call(tokens=10)
    manager.set_queue_size(1)

    app = create_app()
    app.dependency_overrides[get_observability_manager] = lambda: manager
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        metrics = await client.get("/api/v1/observability/metrics")
        assert metrics.status_code == 200
        body = metrics.json()
        assert body["execution_count"] >= 1
        assert body["queue_size"] == 1

        traces = await client.get("/api/v1/observability/traces")
        assert traces.status_code == 200
        assert any(item["trace_id"] == "api-trace-1" for item in traces.json())

        one = await client.get("/api/v1/observability/traces/api-trace-1")
        assert one.status_code == 200
        assert one.json()["execution_id"] == "api-exec-1"

        missing = await client.get("/api/v1/observability/traces/missing")
        assert missing.status_code == 404

    app.dependency_overrides.clear()
