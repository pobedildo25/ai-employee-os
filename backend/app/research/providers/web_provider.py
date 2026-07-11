from typing import Any

from app.research.interfaces.researcher import ResearchProvider
from app.research.models import ResearchSource
from app.research.providers.mock_provider import MockProvider


class WebProvider(ResearchProvider):
    """Web fetch/extract adapter — mock-backed foundation for future HTTP providers."""

    name = "web"

    def __init__(self, backend: ResearchProvider | None = None) -> None:
        self._backend = backend or MockProvider()

    async def search(self, queries: list[str], *, limit: int = 10) -> list[dict[str, Any]]:
        results = await self._backend.search(queries, limit=limit)
        for item in results:
            item.setdefault("source_type", "web")
        return results

    async def fetch(self, url: str) -> dict[str, Any]:
        payload = await self._backend.fetch(url)
        payload["source_type"] = "web"
        return payload

    async def extract(self, payload: dict[str, Any]) -> ResearchSource:
        source = await self._backend.extract(payload)
        return source.model_copy(update={"source_type": "web"})
