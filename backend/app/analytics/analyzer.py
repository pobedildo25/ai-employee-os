import json
import logging
from typing import Any

from app.agents.parsers.response_parser import ResponseParseError, extract_json_content
from app.analytics.analyzers.client_analyzer import ClientAnalyzer
from app.analytics.analyzers.document_analyzer import DocumentAnalyzer
from app.analytics.analyzers.performance_analyzer import PerformanceAnalyzer
from app.analytics.analyzers.project_analyzer import ProjectAnalyzer
from app.analytics.analyzers.quality_analyzer import QualityAnalyzer
from app.analytics.interfaces.analytics import AnalyticsAnalyzerInterface
from app.analytics.models import AnalyticsDataset, AnalyticsInsight, AnalyticsRequest
from app.analytics.prompt import ANALYTICS_SYSTEM_PROMPT, build_analytics_user_message
from app.llm.exceptions import LLMProviderError
from app.llm.gateway import LLMGateway
from app.llm.models import LLMMessage

logger = logging.getLogger(__name__)


class AnalyticsAnalyzer(AnalyticsAnalyzerInterface):
    """Combines domain analyzers with optional LLM interpretation."""

    def __init__(
        self,
        llm_gateway: LLMGateway | None = None,
        *,
        client: ClientAnalyzer | None = None,
        project: ProjectAnalyzer | None = None,
        performance: PerformanceAnalyzer | None = None,
        document: DocumentAnalyzer | None = None,
        quality: QualityAnalyzer | None = None,
    ) -> None:
        self._gateway = llm_gateway
        self._client = client or ClientAnalyzer()
        self._project = project or ProjectAnalyzer()
        self._performance = performance or PerformanceAnalyzer()
        self._document = document or DocumentAnalyzer()
        self._quality = quality or QualityAnalyzer()

    def analyze_heuristics(
        self,
        dataset: AnalyticsDataset,
        metrics: dict[str, Any],
    ) -> list[AnalyticsInsight]:
        insights: list[AnalyticsInsight] = []
        insights.extend(self._client.analyze(dataset, metrics))
        insights.extend(self._project.analyze(dataset, metrics))
        insights.extend(self._performance.analyze(dataset, metrics))
        insights.extend(self._document.analyze(dataset, metrics))
        insights.extend(self._quality.analyze(dataset, metrics))
        return insights

    async def interpret(
        self,
        *,
        request: AnalyticsRequest,
        metrics: dict[str, Any],
        dataset: AnalyticsDataset,
        heuristic_insights: list,
        trace_id: str = "-",
    ) -> dict[str, Any]:
        if self._gateway is None:
            return _fallback_interpretation(metrics, heuristic_insights, dataset)

        messages = [
            LLMMessage(role="system", content=ANALYTICS_SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=build_analytics_user_message(
                    analytics_type=request.analytics_type,
                    metrics=metrics,
                    heuristic_insights=[
                        i.model_dump(mode="json") if hasattr(i, "model_dump") else dict(i)
                        for i in heuristic_insights
                    ],
                    client_intelligence=dataset.client_intelligence,
                    learning_rules=dataset.learning_rules or request.learning_rules,
                    goal=request.goal,
                ),
            ),
        ]
        try:
            response = await self._gateway.complete(messages, temperature=0.2)
            return parse_analytics_interpretation(response.content)
        except (LLMProviderError, ResponseParseError, ValueError, json.JSONDecodeError, Exception) as exc:
            logger.warning("analytics llm interpret degraded | trace_id=%s error=%s", trace_id, exc)
            return _fallback_interpretation(metrics, heuristic_insights, dataset)


def parse_analytics_interpretation(raw: str) -> dict[str, Any]:
    content = extract_json_content(raw)
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ResponseParseError("Analytics interpretation must be an object")
    insights: list[AnalyticsInsight] = []
    for item in data.get("insights") or []:
        if not isinstance(item, dict):
            continue
        insights.append(
            AnalyticsInsight(
                category=str(item.get("category") or "general"),
                title=str(item.get("title") or "Insight"),
                description=str(item.get("description") or ""),
                importance=float(item.get("importance", 0.5)),
                confidence=float(item.get("confidence", 0.7)),
            )
        )
    return {
        "summary": str(data.get("summary") or ""),
        "insights": insights,
        "recommendations": [str(r) for r in (data.get("recommendations") or []) if str(r).strip()],
        "confidence": float(data.get("confidence", 0.7)),
    }


def _fallback_interpretation(
    metrics: dict[str, Any],
    heuristic_insights: list,
    dataset: AnalyticsDataset,
) -> dict[str, Any]:
    quality = metrics.get("quality") or {}
    recommendations: list[str] = []
    if float(quality.get("pass_rate") or 0) >= 0.8:
        recommendations.append("Keep current workflow")
    if float(quality.get("revision_rate") or 0) >= 0.3:
        recommendations.append("Review recurring revision causes with the client")
    for rule in dataset.learning_rules[:3]:
        value = rule.get("value") or rule.get("content") or rule.get("rule")
        if value:
            recommendations.append(f"Honor learning preference: {value}")
    if not recommendations:
        recommendations.append("Continue monitoring metrics and validate with stakeholders")

    summary_parts = []
    client = metrics.get("client") or {}
    if client.get("projects_count") is not None:
        summary_parts.append(f"{client.get('projects_count')} projects")
    if quality.get("pass_rate") is not None:
        summary_parts.append(f"pass rate {float(quality.get('pass_rate') or 0):.0%}")
    summary = "Analytics overview: " + (", ".join(summary_parts) if summary_parts else "limited data")

    confidences = [
        float(getattr(i, "confidence", 0.7) if not isinstance(i, dict) else i.get("confidence", 0.7))
        for i in heuristic_insights
    ] or [0.5]
    return {
        "summary": summary,
        "insights": list(heuristic_insights),
        "recommendations": recommendations,
        "confidence": min(0.95, sum(confidences) / len(confidences)),
    }
