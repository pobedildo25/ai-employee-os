from typing import Any

from app.observability.exporters.console_exporter import ConsoleExporter
from app.observability.exporters.json_exporter import JsonExporter
from app.observability.interfaces.observability import ObservabilityProvider
from app.observability.logger import ObservabilityLogger
from app.observability.metrics import MetricsCollector
from app.observability.models import ExecutionTrace, MetricsSnapshot, TimelineEvent, TraceStatus
from app.observability.providers.in_memory_provider import InMemoryObservabilityProvider
from app.observability.timeline import TimelineService
from app.observability.tracer import TimelineRecorder, Tracer


class ObservabilityManager:
    """Facade for traces, timeline, metrics, and export — no agent decisions."""

    def __init__(self, provider: ObservabilityProvider | None = None) -> None:
        self._provider = provider or InMemoryObservabilityProvider()
        self.tracer = Tracer(self._provider)
        self.timeline = TimelineService(TimelineRecorder(self._provider))
        self.metrics = MetricsCollector(self._provider)
        self.logger = ObservabilityLogger()
        self.json_exporter = JsonExporter(self._provider)
        self.console_exporter = ConsoleExporter(self._provider)

    @property
    def provider(self) -> ObservabilityProvider:
        return self._provider

    async def start_execution(
        self,
        *,
        trace_id: str,
        execution_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionTrace:
        self.logger.bind_trace(trace_id)
        self.logger.info(
            "execution started",
            execution_id=execution_id,
            trace_id=trace_id,
        )
        return await self.tracer.start(
            trace_id=trace_id,
            execution_id=execution_id,
            metadata=metadata,
        )

    async def finish_execution(
        self,
        trace_id: str,
        *,
        status: TraceStatus = TraceStatus.COMPLETED,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionTrace:
        trace = await self.tracer.finish(trace_id, status=status, metadata=metadata)
        self.logger.info(
            "execution finished",
            execution_id=trace.execution_id,
            status=trace.status.value,
            duration_ms=trace.duration_ms,
        )
        return trace

    async def start_node(self, *, trace_id: str, node_name: str) -> TimelineEvent:
        self.logger.debug("node started", node_name=node_name, trace_id=trace_id)
        return await self.timeline.start_event(trace_id=trace_id, node_name=node_name)

    async def finish_node(
        self,
        *,
        trace_id: str,
        node_name: str,
        status: str = "completed",
    ) -> TimelineEvent:
        event = await self.timeline.finish_event(
            trace_id=trace_id,
            node_name=node_name,
            status=status,
        )
        self.logger.debug(
            "node finished",
            node_name=node_name,
            status=status,
            duration_ms=event.duration_ms,
        )
        return event

    async def get_trace(self, trace_id: str) -> ExecutionTrace | None:
        return await self._provider.get_trace(trace_id)

    async def list_traces(self, *, limit: int = 100) -> list[ExecutionTrace]:
        return await self._provider.list_traces(limit=limit)

    def get_metrics(self) -> MetricsSnapshot:
        return self.metrics.snapshot()

    def record_llm_call(self, *, tokens: int = 0) -> None:
        self.metrics.record_llm_call(tokens=tokens)

    def set_queue_size(self, size: int) -> None:
        self.metrics.set_queue_size(size)

    def export_json(self) -> str:
        return self.json_exporter.export()

    def export_console(self) -> dict[str, Any]:
        return self.console_exporter.export()
