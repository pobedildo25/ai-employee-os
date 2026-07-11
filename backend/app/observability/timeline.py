from app.observability.models import ExecutionTimeline, TimelineEvent
from app.observability.tracer import TimelineRecorder


class TimelineService:
    """Assembles and updates ExecutionTimeline records."""

    def __init__(self, recorder: TimelineRecorder) -> None:
        self._recorder = recorder

    async def start_event(self, *, trace_id: str, node_name: str) -> TimelineEvent:
        return await self._recorder.start_node(trace_id=trace_id, node_name=node_name)

    async def finish_event(
        self,
        *,
        trace_id: str,
        node_name: str,
        status: str = "completed",
    ) -> TimelineEvent:
        from app.observability.models import TimelineEventStatus

        return await self._recorder.finish_node(
            trace_id=trace_id,
            node_name=node_name,
            status=TimelineEventStatus(status),
        )

    @staticmethod
    def empty(trace_id: str, execution_id: str) -> ExecutionTimeline:
        return ExecutionTimeline(trace_id=trace_id, execution_id=execution_id)
