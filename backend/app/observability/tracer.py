from datetime import datetime
from typing import Any

from app.observability.interfaces.observability import ObservabilityProvider
from app.observability.models import (
    ExecutionTimeline,
    ExecutionTrace,
    TimelineEvent,
    TimelineEventStatus,
    TraceStatus,
)


class Tracer:
    """Starts and finishes execution traces — observation only."""

    def __init__(self, provider: ObservabilityProvider) -> None:
        self._provider = provider

    async def start(
        self,
        *,
        trace_id: str,
        execution_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionTrace:
        trace = ExecutionTrace(
            trace_id=trace_id,
            execution_id=execution_id,
            status=TraceStatus.RUNNING,
            metadata=metadata or {},
            timeline=ExecutionTimeline(trace_id=trace_id, execution_id=execution_id),
        )
        return await self._provider.save_trace(trace)

    async def finish(
        self,
        trace_id: str,
        *,
        status: TraceStatus = TraceStatus.COMPLETED,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionTrace:
        trace = await self._provider.get_trace(trace_id)
        if trace is None:
            raise ValueError(f"Trace not found: {trace_id}")
        finished_at = datetime.now()
        trace.finished_at = finished_at
        trace.status = status
        trace.duration_ms = (finished_at - trace.started_at).total_seconds() * 1000
        if metadata:
            trace.metadata.update(metadata)
        await self._provider.save_trace(trace)
        self._provider.record_execution(
            failed=status == TraceStatus.FAILED,
            duration_ms=trace.duration_ms or 0.0,
        )
        return trace


class TimelineRecorder:
    """Records per-node timeline events without changing workflow logic."""

    def __init__(self, provider: ObservabilityProvider) -> None:
        self._provider = provider
        self._open_events: dict[tuple[str, str], TimelineEvent] = {}

    async def start_node(
        self,
        *,
        trace_id: str,
        node_name: str,
        metadata: dict[str, Any] | None = None,
    ) -> TimelineEvent:
        event = TimelineEvent(
            node_name=node_name,
            status=TimelineEventStatus.STARTED,
            metadata=metadata or {},
        )
        saved = await self._provider.save_timeline_event(trace_id, event)
        self._open_events[(trace_id, node_name)] = saved
        return saved

    async def finish_node(
        self,
        *,
        trace_id: str,
        node_name: str,
        status: TimelineEventStatus = TimelineEventStatus.COMPLETED,
        metadata: dict[str, Any] | None = None,
    ) -> TimelineEvent:
        key = (trace_id, node_name)
        event = self._open_events.pop(key, None)
        if event is None:
            event = TimelineEvent(node_name=node_name, status=TimelineEventStatus.STARTED)

        finished_at = datetime.now()
        event.finished_at = finished_at
        event.duration_ms = (finished_at - event.started_at).total_seconds() * 1000
        event.status = status
        if metadata:
            event.metadata.update(metadata)
        return await self._provider.save_timeline_event(trace_id, event)
