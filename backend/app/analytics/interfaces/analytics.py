from abc import ABC, abstractmethod
from typing import Any

from app.analytics.models import AnalyticsDataset, AnalyticsRequest, AnalyticsResult


class AnalyticsDataProvider(ABC):
    """Read-only adapter over existing system sources."""

    name: str

    @abstractmethod
    async def fetch(self, request: AnalyticsRequest) -> dict[str, Any]:
        raise NotImplementedError


class AnalyticsManagerInterface(ABC):
    @abstractmethod
    async def run(self, request: AnalyticsRequest, *, trace_id: str = "-") -> AnalyticsResult:
        raise NotImplementedError


class AnalyticsAnalyzerInterface(ABC):
    @abstractmethod
    async def interpret(
        self,
        *,
        request: AnalyticsRequest,
        metrics: dict[str, Any],
        dataset: AnalyticsDataset,
        heuristic_insights: list,
        trace_id: str = "-",
    ) -> dict[str, Any]:
        raise NotImplementedError
