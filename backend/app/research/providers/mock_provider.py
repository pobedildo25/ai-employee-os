from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from app.research.interfaces.researcher import ResearchProvider
from app.research.models import ResearchSource


class MockProvider(ResearchProvider):
    """Deterministic mock sources — swappable for real APIs later."""

    name = "mock"

    def __init__(self, seeded: list[dict[str, Any]] | None = None) -> None:
        self._seeded = seeded

    async def search(self, queries: list[str], *, limit: int = 10) -> list[dict[str, Any]]:
        if self._seeded is not None:
            return self._seeded[:limit]
        primary = queries[0] if queries else "research"
        now = datetime.utcnow()
        catalog = [
            {
                "title": f"Market overview: {primary}",
                "url": f"https://example.com/market/{uuid4().hex[:8]}",
                "source_type": "report",
                "snippet": f"Analysts report growing demand related to {primary}.",
                "published_at": (now - timedelta(days=14)).isoformat(),
                "domain_trust": 0.82,
            },
            {
                "title": f"Competitor landscape for {primary}",
                "url": f"https://example.com/competitors/{uuid4().hex[:8]}",
                "source_type": "article",
                "snippet": f"Company A launched a product competing in {primary}.",
                "published_at": (now - timedelta(days=30)).isoformat(),
                "domain_trust": 0.74,
            },
            {
                "title": f"Trend brief: {primary}",
                "url": f"https://example.com/trends/{uuid4().hex[:8]}",
                "source_type": "blog",
                "snippet": f"Emerging trends around {primary} include automation and personalization.",
                "published_at": (now - timedelta(days=7)).isoformat(),
                "domain_trust": 0.68,
            },
            {
                "title": f"Industry news: {primary}",
                "url": f"https://news.example.com/{uuid4().hex[:8]}",
                "source_type": "news",
                "snippet": f"Recent coverage highlights adoption challenges for {primary}.",
                "published_at": (now - timedelta(days=3)).isoformat(),
                "domain_trust": 0.7,
            },
        ]
        return catalog[:limit]

    async def fetch(self, url: str) -> dict[str, Any]:
        return {
            "url": url,
            "title": f"Fetched page {url}",
            "content": f"Extracted page content from {url}.",
            "fetched_at": datetime.utcnow().isoformat(),
        }

    async def extract(self, payload: dict[str, Any]) -> ResearchSource:
        published = payload.get("published_at")
        published_at = None
        if isinstance(published, str):
            try:
                published_at = datetime.fromisoformat(published.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                published_at = None
        content = str(
            payload.get("extracted_content")
            or payload.get("content")
            or payload.get("snippet")
            or ""
        )
        return ResearchSource(
            title=str(payload.get("title") or "Untitled source"),
            url=payload.get("url"),
            source_type=str(payload.get("source_type") or "web"),
            extracted_content=content,
            credibility_score=float(payload.get("domain_trust") or payload.get("credibility_score") or 0.6),
            published_at=published_at,
            metadata={k: v for k, v in payload.items() if k not in {"title", "url", "snippet", "content"}},
        )
