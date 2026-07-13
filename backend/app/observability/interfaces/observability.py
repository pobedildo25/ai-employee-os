from abc import ABC, abstractmethod
from typing import Any

from app.observability.models import ExecutionTrace, MetricsSnapshot, TimelineEvent


class ObservabilityProvider(ABC):
    @abstractmethod
    async def save_trace(self, trace: ExecutionTrace) -> ExecutionTrace:
        raise NotImplementedError

    @abstractmethod
    async def get_trace(self, trace_id: str) -> ExecutionTrace | None:
        raise NotImplementedError

    @abstractmethod
    async def list_traces(self, *, limit: int = 100) -> list[ExecutionTrace]:
        raise NotImplementedError

    @abstractmethod
    async def save_timeline_event(
        self,
        trace_id: str,
        event: TimelineEvent,
    ) -> TimelineEvent:
        raise NotImplementedError

    @abstractmethod
    def get_metrics(self) -> MetricsSnapshot:
        raise NotImplementedError

    @abstractmethod
    def record_execution(self, *, failed: bool = False, duration_ms: float = 0.0) -> None:
        raise NotImplementedError

    @abstractmethod
    def record_llm_call(
        self,
        *,
        tokens: int = 0,
        latency_ms: float = 0.0,
        failed: bool = False,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def set_queue_size(self, size: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def export_payload(self) -> dict[str, Any]:
        raise NotImplementedError
