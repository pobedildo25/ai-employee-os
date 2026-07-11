from abc import ABC, abstractmethod
from typing import Any

from app.research.models import ResearchRequest, ResearchResult, ResearchSource


class ResearchProvider(ABC):
    """External research adapter — search/fetch/extract only, not a browser."""

    name: str

    @abstractmethod
    async def search(self, queries: list[str], *, limit: int = 10) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def fetch(self, url: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def extract(self, payload: dict[str, Any]) -> ResearchSource:
        raise NotImplementedError


class ResearcherInterface(ABC):
    @abstractmethod
    async def research(self, request: ResearchRequest, *, trace_id: str = "-") -> ResearchResult:
        raise NotImplementedError


class ResearchManagerInterface(ABC):
    @abstractmethod
    async def run(self, request: ResearchRequest, *, trace_id: str = "-") -> ResearchResult:
        raise NotImplementedError

    @abstractmethod
    def get_result(self, research_id: str) -> ResearchResult | None:
        raise NotImplementedError
