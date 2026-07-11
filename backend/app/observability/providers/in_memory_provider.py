from datetime import datetime
from typing import Any

from app.observability.interfaces.observability import ObservabilityProvider
from app.observability.models import (
    ExecutionTimeline,
    ExecutionTrace,
    MetricsSnapshot,
    TimelineEvent,
    TraceStatus,
)
from app.observability.policies.retention_policy import RetentionPolicy


class InMemoryObservabilityProvider(ObservabilityProvider):
    """Process-local observability store — no external backends."""

    def __init__(self, retention: RetentionPolicy | None = None) -> None:
        self._retention = retention or RetentionPolicy()
        self._traces: dict[str, ExecutionTrace] = {}
        self._execution_count = 0
        self._failed_count = 0
        self._duration_total_ms = 0.0
        self._llm_calls = 0
        self._tokens = 0
        self._queue_size = 0

    async def save_trace(self, trace: ExecutionTrace) -> ExecutionTrace:
        if trace.timeline is None:
            trace.timeline = ExecutionTimeline(
                trace_id=trace.trace_id,
                execution_id=trace.execution_id,
            )
        self._traces[trace.trace_id] = trace
        self._enforce_retention()
        return trace

    async def get_trace(self, trace_id: str) -> ExecutionTrace | None:
        return self._traces.get(trace_id)

    async def list_traces(self, *, limit: int = 100) -> list[ExecutionTrace]:
        traces = sorted(self._traces.values(), key=lambda item: item.started_at, reverse=True)
        return traces[:limit]

    async def save_timeline_event(self, trace_id: str, event: TimelineEvent) -> TimelineEvent:
        trace = self._traces.get(trace_id)
        if trace is None:
            raise ValueError(f"Trace not found: {trace_id}")
        if trace.timeline is None:
            trace.timeline = ExecutionTimeline(
                trace_id=trace.trace_id,
                execution_id=trace.execution_id,
            )
        existing = next((item for item in trace.timeline.events if item.id == event.id), None)
        if existing is None:
            trace.timeline.events.append(event)
        else:
            index = trace.timeline.events.index(existing)
            trace.timeline.events[index] = event
        self._traces[trace_id] = trace
        return event

    def get_metrics(self) -> MetricsSnapshot:
        completed = [
            trace
            for trace in self._traces.values()
            if trace.status in {TraceStatus.COMPLETED, TraceStatus.FAILED, TraceStatus.CANCELLED}
        ]
        active = [
            trace
            for trace in self._traces.values()
            if trace.status in {TraceStatus.STARTED, TraceStatus.RUNNING}
        ]
        average = (
            self._duration_total_ms / self._execution_count if self._execution_count else 0.0
        )
        return MetricsSnapshot(
            execution_count=self._execution_count,
            failed_count=self._failed_count,
            average_duration_ms=average,
            llm_calls=self._llm_calls,
            tokens=self._tokens,
            queue_size=self._queue_size,
            active_traces=len(active),
            completed_traces=len(completed),
        )

    def record_execution(self, *, failed: bool = False, duration_ms: float = 0.0) -> None:
        self._execution_count += 1
        self._duration_total_ms += max(0.0, duration_ms)
        if failed:
            self._failed_count += 1

    def record_llm_call(self, *, tokens: int = 0) -> None:
        self._llm_calls += 1
        self._tokens += max(0, tokens)

    def set_queue_size(self, size: int) -> None:
        self._queue_size = max(0, size)

    def export_payload(self) -> dict[str, Any]:
        return {
            "metrics": self.get_metrics().model_dump(mode="json"),
            "traces": [trace.model_dump(mode="json") for trace in self._traces.values()],
            "exported_at": datetime.now().isoformat(),
        }

    def _enforce_retention(self) -> None:
        overflow = len(self._traces) - self._retention.max_traces
        if overflow <= 0:
            return
        for trace_id in self._retention.select_eviction_ids(list(self._traces.values()), overflow=overflow):
            self._traces.pop(trace_id, None)
