import json
import logging
from typing import Any

from app.agents.parsers.response_parser import ResponseParseError, extract_json_content
from app.llm.exceptions import LLMProviderError
from app.llm.gateway import LLMGateway
from app.llm.models import LLMMessage
from app.research.analyzers import run_type_analyzers
from app.research.interfaces.researcher import ResearchProvider, ResearcherInterface
from app.research.models import (
    ResearchFinding,
    ResearchInsight,
    ResearchRequest,
    ResearchResult,
    ResearchSource,
)
from app.research.prompt import RESEARCH_SYSTEM_PROMPT, build_research_user_message
from app.research.query_builder import ResearchQueryBuilder
from app.research.source_ranker import SourceRanker

logger = logging.getLogger(__name__)


class Researcher(ResearcherInterface):
    """Aggregates external sources and interprets them via LLM — not a browser."""

    def __init__(
        self,
        provider: ResearchProvider,
        *,
        llm_gateway: LLMGateway | None = None,
        query_builder: ResearchQueryBuilder | None = None,
        ranker: SourceRanker | None = None,
    ) -> None:
        self._provider = provider
        self._gateway = llm_gateway
        self._query_builder = query_builder or ResearchQueryBuilder()
        self._ranker = ranker or SourceRanker()

    async def research(self, request: ResearchRequest, *, trace_id: str = "-") -> ResearchResult:
        queries = self._query_builder.build(request)
        try:
            raw_hits = await self._provider.search(queries, limit=request.max_sources)
        except Exception as exc:
            logger.warning("research provider search degraded | trace_id=%s error=%s", trace_id, exc)
            raw_hits = []
        sources: list[ResearchSource] = []
        for hit in raw_hits:
            if hit.get("url") and not hit.get("extracted_content") and not hit.get("snippet"):
                try:
                    fetched = await self._provider.fetch(str(hit["url"]))
                    hit = {**hit, **fetched}
                except Exception as exc:
                    logger.warning(
                        "research provider fetch degraded | trace_id=%s url=%s error=%s",
                        trace_id,
                        hit.get("url"),
                        exc,
                    )
            try:
                sources.append(await self._provider.extract(hit))
            except Exception as exc:
                logger.warning("research provider extract degraded | trace_id=%s error=%s", trace_id, exc)

        ranked = self._ranker.rank(sources, query=request.query)[: request.max_sources]
        heuristic = run_type_analyzers(request.research_type, ranked, query=request.query)
        interpretation = await self._interpret(request, ranked, heuristic, trace_id=trace_id)

        findings = list(interpretation.get("findings") or [])
        if not findings:
            findings = [
                ResearchFinding(
                    title=source.title,
                    description=source.extracted_content[:280] or source.title,
                    source_urls=[source.url] if source.url else [],
                    confidence=source.credibility_score,
                )
                for source in ranked[:5]
            ]

        insights = _merge_insights(heuristic, list(interpretation.get("insights") or []))
        recommendations = list(interpretation.get("recommendations") or [])
        if not recommendations:
            recommendations = ["Use findings as input for strategy_analysis"]

        confidences = [i.confidence for i in insights] + [s.credibility_score for s in ranked]
        confidence = float(interpretation.get("confidence") or (sum(confidences) / len(confidences) if confidences else 0.5))

        return ResearchResult(
            research_type=request.research_type,
            query=request.query,
            search_queries=queries,
            summary=str(interpretation.get("summary") or _default_summary(request, ranked)),
            sources=ranked,
            findings=findings,
            insights=insights,
            recommendations=list(dict.fromkeys(recommendations)),
            confidence=min(0.95, max(0.0, confidence)),
            metadata={
                "provider": getattr(self._provider, "name", "unknown"),
                "source_count": len(ranked),
                "status": "ready",
            },
        )

    async def _interpret(
        self,
        request: ResearchRequest,
        sources: list[ResearchSource],
        heuristic: list[ResearchInsight],
        *,
        trace_id: str,
    ) -> dict[str, Any]:
        if self._gateway is None:
            return _fallback(request, sources, heuristic)

        messages = [
            LLMMessage(role="system", content=RESEARCH_SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=build_research_user_message(
                    query=request.query,
                    research_type=request.research_type,
                    sources=[s.model_dump(mode="json") for s in sources],
                    heuristic_insights=[i.model_dump(mode="json") for i in heuristic],
                    context=request.context,
                    constraints=request.constraints,
                ),
            ),
        ]
        try:
            response = await self._gateway.complete(messages, temperature=0.2)
            return parse_research_interpretation(response.content)
        except (LLMProviderError, ResponseParseError, ValueError, json.JSONDecodeError, Exception) as exc:
            logger.warning("research llm interpret degraded | trace_id=%s error=%s", trace_id, exc)
            return _fallback(request, sources, heuristic)


def parse_research_interpretation(raw: str) -> dict[str, Any]:
    content = extract_json_content(raw)
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ResponseParseError("Research interpretation must be an object")

    findings: list[ResearchFinding] = []
    for item in data.get("findings") or []:
        if not isinstance(item, dict):
            continue
        findings.append(
            ResearchFinding(
                title=str(item.get("title") or "Finding"),
                description=str(item.get("description") or ""),
                source_urls=[str(u) for u in (item.get("source_urls") or [])],
                confidence=float(item.get("confidence", 0.7)),
            )
        )
    insights: list[ResearchInsight] = []
    for item in data.get("insights") or []:
        if not isinstance(item, dict):
            continue
        insights.append(
            ResearchInsight(
                category=str(item.get("category") or "general"),
                title=str(item.get("title") or "Insight"),
                description=str(item.get("description") or ""),
                importance=float(item.get("importance", 0.5)),
                confidence=float(item.get("confidence", 0.7)),
            )
        )
    return {
        "summary": str(data.get("summary") or ""),
        "findings": findings,
        "insights": insights,
        "recommendations": [str(r) for r in (data.get("recommendations") or []) if str(r).strip()],
        "confidence": float(data.get("confidence", 0.7)),
    }


def _fallback(
    request: ResearchRequest,
    sources: list[ResearchSource],
    heuristic: list[ResearchInsight],
) -> dict[str, Any]:
    return {
        "summary": _default_summary(request, sources),
        "findings": [
            ResearchFinding(
                title=s.title,
                description=s.extracted_content[:280] or s.title,
                source_urls=[s.url] if s.url else [],
                confidence=s.credibility_score,
            )
            for s in sources[:5]
        ],
        "insights": heuristic,
        "recommendations": [
            "Feed research into strategy_analysis",
            "Validate top sources with the client",
        ],
        "confidence": 0.65,
    }


def _default_summary(request: ResearchRequest, sources: list[ResearchSource]) -> str:
    return (
        f"{request.research_type.value.replace('_', ' ').title()} on '{request.query}' "
        f"using {len(sources)} source(s)"
    )


def _merge_insights(
    primary: list[ResearchInsight],
    secondary: list[ResearchInsight],
) -> list[ResearchInsight]:
    seen: set[tuple[str, str]] = set()
    result: list[ResearchInsight] = []
    for insight in list(primary) + list(secondary):
        if isinstance(insight, dict):
            insight = ResearchInsight.model_validate(insight)
        key = (insight.category, insight.title)
        if key in seen:
            continue
        seen.add(key)
        result.append(insight)
    return result
