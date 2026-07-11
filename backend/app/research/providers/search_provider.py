from typing import Any

from app.research.interfaces.researcher import ResearchProvider
from app.research.models import ResearchSource
from app.research.providers.mock_provider import MockProvider


class SearchProvider(ResearchProvider):
    """Search-oriented adapter — currently delegates to mock, ready for real search APIs."""

    name = "search"

    def __init__(self, backend: ResearchProvider | None = None) -> None:
        self._backend = backend or MockProvider()

    async def search(self, queries: list[str], *, limit: int = 10) -> list[dict[str, Any]]:
        return await self._backend.search(queries, limit=limit)

    async def fetch(self, url: str) -> dict[str, Any]:
        return await self._backend.fetch(url)

    async def extract(self, payload: dict[str, Any]) -> ResearchSource:
        source = await self._backend.extract(payload)
        return source.model_copy(update={"source_type": source.source_type or "search"})
