from app.analytics.analyzer import AnalyticsAnalyzer
from app.analytics.interfaces.analytics import AnalyticsManagerInterface
from app.analytics.memory_preparer import prepare_analytics_memory_items
from app.analytics.metrics import compute_all_metrics
from app.analytics.models import AnalyticsInsight, AnalyticsRequest, AnalyticsResult
from app.analytics.providers.data_provider import CompositeAnalyticsDataProvider
from app.analytics.query_builder import AnalyticsQueryBuilder
from app.analytics.validators.analytics_validator import AnalyticsValidator, result_to_document_ast


class AnalyticsManager(AnalyticsManagerInterface):
    """Runs read-only analytics over existing sources — does not store its own data."""

    def __init__(
        self,
        *,
        query_builder: AnalyticsQueryBuilder | None = None,
        analyzer: AnalyticsAnalyzer | None = None,
        validator: AnalyticsValidator | None = None,
        data_provider: CompositeAnalyticsDataProvider | None = None,
    ) -> None:
        self._query_builder = query_builder or AnalyticsQueryBuilder(data_provider)
        self._analyzer = analyzer or AnalyticsAnalyzer()
        self._validator = validator or AnalyticsValidator()

    async def run(self, request: AnalyticsRequest, *, trace_id: str = "-") -> AnalyticsResult:
        request_errors = self._validator.validate_request(request)
        if request_errors:
            return AnalyticsResult(
                analytics_type=request.analytics_type,
                analysis_warnings=request_errors,
                metadata={"status": "invalid_request"},
            )

        dataset = await self._query_builder.build(request)
        metrics = compute_all_metrics(dataset)
        heuristic = self._analyzer.analyze_heuristics(dataset, metrics)
        interpretation = await self._analyzer.interpret(
            request=request,
            metrics=metrics,
            dataset=dataset,
            heuristic_insights=heuristic,
            trace_id=trace_id,
        )

        llm_insights = list(interpretation.get("insights") or [])
        merged_insights = _merge_insights(heuristic, llm_insights)
        recommendations = list(interpretation.get("recommendations") or [])
        if not recommendations:
            recommendations = ["Continue monitoring and validate with stakeholders"]

        # Learning preferences may shape recommendations without changing metrics.
        for rule in dataset.learning_rules:
            value = str(rule.get("value") or rule.get("content") or "")
            if value and ("без таблиц" in value.lower() or "without tables" in value.lower()):
                recommendations.insert(0, "Prefer narrative report format without tables")

        result = AnalyticsResult(
            analytics_type=request.analytics_type,
            summary=str(interpretation.get("summary") or ""),
            metrics=metrics,
            insights=merged_insights,
            recommendations=list(dict.fromkeys(recommendations)),
            confidence=float(interpretation.get("confidence") or 0.5),
            metadata={
                "status": "ready",
                "sources_used": dataset.sources_used,
                "document_type": "docx",
                "presentation_ready": True,
            },
        )

        warnings = self._validator.validate_result(result)
        result.analysis_warnings = warnings
        if warnings and (not result.metrics or not result.insights):
            result.metadata["status"] = "incomplete"
            return result

        document_ast = result_to_document_ast(result)
        result.document_ast = document_ast.model_dump(mode="json")
        memory_items = prepare_analytics_memory_items(
            result,
            client_id=request.client_id,
            project_id=request.project_id,
        )
        result.memory_candidates = [item.model_dump(mode="json") for item in memory_items]
        return result


def _merge_insights(
    primary: list[AnalyticsInsight],
    secondary: list[AnalyticsInsight],
) -> list[AnalyticsInsight]:
    seen: set[tuple[str, str]] = set()
    result: list[AnalyticsInsight] = []
    for insight in list(primary) + list(secondary):
        if isinstance(insight, dict):
            insight = AnalyticsInsight.model_validate(insight)
        key = (insight.category, insight.title)
        if key in seen:
            continue
        seen.add(key)
        result.append(insight)
    return result
