from app.observability.interfaces.observability import ObservabilityProvider
from app.observability.models import MetricsSnapshot


class MetricsCollector:
    """In-memory metrics facade — observation only."""

    def __init__(self, provider: ObservabilityProvider) -> None:
        self._provider = provider

    def snapshot(self) -> MetricsSnapshot:
        return self._provider.get_metrics()

    def record_execution(self, *, failed: bool = False, duration_ms: float = 0.0) -> None:
        self._provider.record_execution(failed=failed, duration_ms=duration_ms)

    def record_llm_call(self, *, tokens: int = 0, latency_ms: float = 0.0, failed: bool = False) -> None:
        self._provider.record_llm_call(tokens=tokens, latency_ms=latency_ms, failed=failed)

    def set_queue_size(self, size: int) -> None:
        self._provider.set_queue_size(size)
