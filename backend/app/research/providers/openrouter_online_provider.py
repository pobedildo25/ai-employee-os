"""Live research via OpenRouter online-capable models (e.g. Perplexity Sonar)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import urlparse

from app.llm.gateway import LLMGateway
from app.llm.models import LLMMessage
from app.research.interfaces.researcher import ResearchProvider
from app.research.models import ResearchSource

logger = logging.getLogger(__name__)


class OpenRouterOnlineProvider(ResearchProvider):
    name = "openrouter_online"

    def __init__(
        self,
        llm_gateway: LLMGateway,
        *,
        model: str = "perplexity/sonar",
    ) -> None:
        self._gateway = llm_gateway
        self._model = model

    async def search(self, queries: list[str], *, limit: int = 10) -> list[dict[str, Any]]:
        query = " | ".join(q for q in queries if q).strip()
        if not query:
            return []

        prompt = (
            "Do live web research for the query below. "
            "Return ONLY valid JSON array of up to "
            f"{limit} objects with keys: title, url, snippet, published_at (nullable). "
            "Prefer primary sources. No markdown fences.\n\n"
            f"Query: {query}"
        )
        try:
            response = await self._gateway.complete(
                messages=[
                    LLMMessage(role="system", content="You are a research assistant with web access."),
                    LLMMessage(role="user", content=prompt),
                ],
                model=self._model,
                temperature=0.2,
                metadata={"use_heavy_model": False, "task": "research_online"},
            )
        except Exception as exc:
            logger.warning("openrouter online research failed: %s", exc)
            return []

        return _parse_search_payload(response.content, limit=limit)

    async def fetch(self, url: str) -> dict[str, Any]:
        return {"url": url, "content": "", "status": "unsupported"}

    async def extract(self, payload: dict[str, Any]) -> ResearchSource:
        return ResearchSource(
            title=str(payload.get("title") or "Source"),
            url=str(payload.get("url") or "") or None,
            extracted_content=str(payload.get("snippet") or payload.get("content") or ""),
            source_type="web",
            metadata={"provider": self.name, "published_at": payload.get("published_at")},
        )


def _parse_search_payload(content: str, *, limit: int) -> list[dict[str, Any]]:
    text = (content or "").strip()
    if not text:
        return []

    fence = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", text, flags=re.DOTALL)
        if not match:
            return [
                {
                    "title": "Research notes",
                    "url": "",
                    "snippet": text[:1200],
                    "source_type": "web",
                }
            ]
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return [
                {
                    "title": "Research notes",
                    "url": "",
                    "snippet": text[:1200],
                    "source_type": "web",
                }
            ]

    if isinstance(parsed, dict):
        parsed = parsed.get("results") or parsed.get("sources") or [parsed]
    if not isinstance(parsed, list):
        return []

    results: list[dict[str, Any]] = []
    for item in parsed[:limit]:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if url and not urlparse(url).scheme:
            url = f"https://{url}"
        results.append(
            {
                "title": str(item.get("title") or url or "Source"),
                "url": url,
                "snippet": str(item.get("snippet") or item.get("content") or "")[:2000],
                "published_at": item.get("published_at"),
                "source_type": "web",
            }
        )
    return results
