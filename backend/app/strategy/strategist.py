from app.strategy.analyzer import StrategyAnalyzer
from app.strategy.interfaces.strategist import StrategyStrategistInterface
from app.strategy.models import StrategyRequest, StrategyResult
from app.strategy.planner import StrategyPlanner
from app.strategy.validators.strategy_validator import StrategyValidator, result_to_document_ast


class StrategyStrategist(StrategyStrategistInterface):
    """Builds strategy insights and DocumentAST for downstream creation/render."""

    def __init__(
        self,
        planner: StrategyPlanner,
        analyzer: StrategyAnalyzer | None = None,
        validator: StrategyValidator | None = None,
    ) -> None:
        self._planner = planner
        self._analyzer = analyzer or StrategyAnalyzer()
        self._validator = validator or StrategyValidator()

    async def analyze(self, request: StrategyRequest, *, trace_id: str = "-") -> StrategyResult:
        request_errors = self._validator.validate_request(request)
        if request_errors:
            return StrategyResult(
                summary="",
                missing_information=request_errors,
                analysis_warnings=request_errors,
                metadata={"status": "invalid_request", "brand_profile": request.brand_profile},
            )

        result = await self._planner.plan(request, trace_id=trace_id)
        # Brand is passed through only — never applied here.
        if request.brand_profile:
            result.metadata["brand_profile"] = request.brand_profile
            result.metadata["brand_profile_passthrough"] = True

        result_errors = self._validator.validate_result(result)
        warnings = self._analyzer.analyze(result)
        if result_errors:
            result.analysis_warnings = result_errors + warnings
            result.missing_information = list(dict.fromkeys(result.missing_information + result_errors))
            result.metadata["status"] = "incomplete"
            return result

        document_ast = result_to_document_ast(result, title=request.metadata.get("title"))
        result.document_ast = document_ast.model_dump(mode="json")
        result.analysis_warnings = warnings
        result.metadata["status"] = "ready"
        result.metadata["document_type"] = "docx"
        return result
