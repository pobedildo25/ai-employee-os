from app.observability.models import ExecutionTrace


class RetentionPolicy:
    """Limits in-memory observability retention — observation only."""

    def __init__(self, max_traces: int = 500) -> None:
        if max_traces < 1:
            raise ValueError("max_traces must be >= 1")
        self.max_traces = max_traces

    def should_evict(self, current_count: int) -> bool:
        return current_count > self.max_traces

    def select_eviction_ids(self, traces: list[ExecutionTrace], *, overflow: int) -> list[str]:
        if overflow <= 0:
            return []
        ordered = sorted(traces, key=lambda trace: trace.started_at)
        return [trace.trace_id for trace in ordered[:overflow]]
