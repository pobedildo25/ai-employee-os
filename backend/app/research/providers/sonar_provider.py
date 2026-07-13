"""Perplexity Sonar via OpenRouter — live web research (citations + search_results)."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import Settings
from app.llm.exceptions import (
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMProviderError,
    LLMRateLimitError,
)
from app.research.interfaces.researcher import ResearchProvider
from app.research.models import ResearchSource

logger = logging.getLogger(__name__)

_RETRYABLE = frozenset({429, 500, 502, 503, 504})


class SonarResearchProvider(ResearchProvider):
    """Uses OpenRouter ``perplexity/sonar*`` chat completions as the research backend.

    Not a headless browser: Sonar performs grounded web search and returns an answer
    with citations / search_results, which we map into ResearchProvider hits.
    """

    name = "sonar"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = (settings.research_sonar_model or "perplexity/sonar").strip()
        self._last_answer: str = ""

    async def search(self, queries: list[str], *, limit: int = 10) -> list[dict[str, Any]]:
        query_text = " | ".join(q.strip() for q in queries if q and str(q).strip())
        if not query_text:
            return []

        payload = await self._complete(
            [
                {
                    "role": "system",
                    "content": (
                        "You are a market research analyst with live web access. "
                        "Answer with grounded facts, cite sources, and prefer recent data. "
                        "Structure the answer with clear findings and implications."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Research query:\n{query_text}\n\n"
                        "Provide a concise research brief with key findings and sourceable claims."
                    ),
                },
            ]
        )
        content = str(payload.get("content") or "").strip()
        self._last_answer = content
        citations = list(payload.get("citations") or [])
        search_results = list(payload.get("search_results") or [])

        hits: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        if content:
            hits.append(
                {
                    "title": "Sonar research synthesis",
                    "url": None,
                    "source_type": "sonar_answer",
                    "snippet": content[:400],
                    "extracted_content": content,
                    "domain_trust": 0.78,
                    "metadata": {"provider": "sonar", "model": self._model},
                }
            )

        for item in search_results:
            if not isinstance(item, dict):
                continue
            url = _as_url(item.get("url"))
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            title = str(item.get("title") or _domain_title(url) or "Web source")
            snippet = str(item.get("snippet") or item.get("content") or "")
            hits.append(
                {
                    "title": title,
                    "url": url,
                    "source_type": "web",
                    "snippet": snippet[:500],
                    "extracted_content": snippet,
                    "published_at": item.get("date") or item.get("published_at"),
                    "domain_trust": 0.72,
                    "metadata": {"provider": "sonar", "raw": item},
                }
            )

        for citation in citations:
            url = _as_url(citation if isinstance(citation, str) else None)
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            hits.append(
                {
                    "title": _domain_title(url) or "Cited source",
                    "url": url,
                    "source_type": "web",
                    "snippet": "",
                    "extracted_content": "",
                    "domain_trust": 0.7,
                    "metadata": {"provider": "sonar", "from_citations": True},
                }
            )

        return hits[: max(1, limit)]

    async def fetch(self, url: str) -> dict[str, Any]:
        # Sonar already returns grounded snippets; no separate HTTP fetch.
        return {
            "url": url,
            "title": _domain_title(url) or "Cited source",
            "content": "",
            "source_type": "web",
        }

    async def extract(self, payload: dict[str, Any]) -> ResearchSource:
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
            credibility_score=float(
                payload.get("domain_trust") or payload.get("credibility_score") or 0.7
            ),
            metadata={
                k: v
                for k, v in payload.items()
                if k
                not in {
                    "title",
                    "url",
                    "snippet",
                    "content",
                    "extracted_content",
                    "domain_trust",
                    "credibility_score",
                }
            },
        )

    async def _complete(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        key = (self._settings.openrouter_api_key or "").strip()
        if not key or key == "change-me":
            raise LLMConfigurationError("OPENROUTER_API_KEY is not set for Sonar research")

        body = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        url = f"{self._settings.openrouter_base_url.rstrip('/')}/chat/completions"

        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(url, json=body, headers=headers)

        if response.status_code == 401:
            raise LLMAuthenticationError("OpenRouter authentication failed")
        if response.status_code == 429:
            raise LLMRateLimitError("OpenRouter rate limit exceeded")
        if response.status_code in _RETRYABLE:
            raise LLMProviderError(
                f"OpenRouter Sonar error {response.status_code}: {response.text[:500]}"
            )
        if response.status_code >= 400:
            raise LLMProviderError(
                f"OpenRouter Sonar error {response.status_code}: {response.text[:500]}"
            )

        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError(f"Unexpected Sonar response format: {exc}") from exc

        citations = data.get("citations") or []
        search_results = data.get("search_results") or []
        # Some OpenRouter routes nest citations under message / annotations.
        message = (data.get("choices") or [{}])[0].get("message") or {}
        if not citations and isinstance(message.get("annotations"), list):
            for ann in message["annotations"]:
                if isinstance(ann, dict) and ann.get("url"):
                    citations.append(ann["url"])

        logger.info(
            "sonar research completed | model=%s citations=%d search_results=%d",
            data.get("model", self._model),
            len(citations) if isinstance(citations, list) else 0,
            len(search_results) if isinstance(search_results, list) else 0,
        )
        return {
            "content": content,
            "citations": citations if isinstance(citations, list) else [],
            "search_results": search_results if isinstance(search_results, list) else [],
            "model": data.get("model", self._model),
        }


def _as_url(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text.startswith(("http://", "https://")):
        return None
    return text


def _domain_title(url: str | None) -> str | None:
    if not url:
        return None
    try:
        host = urlparse(url).netloc
    except Exception:
        return None
    return host or None
