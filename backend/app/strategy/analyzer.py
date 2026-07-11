from app.strategy.models import StrategyResult


class StrategyAnalyzer:
    """Soft structural checks for strategy outputs — no business decisions."""

    def analyze(self, result: StrategyResult) -> list[str]:
        warnings: list[str] = []
        if not result.summary.strip() and not result.insights:
            warnings.append("Strategy summary and insights are both empty")
        if not result.insights:
            warnings.append("Strategy has no insights")
        if not result.recommendations:
            warnings.append("Strategy has no recommendations")
        if result.sections and len(result.sections) < 2:
            warnings.append("Strategy document structure is thin")
        low_confidence = [i for i in result.insights if i.confidence < 0.4]
        if low_confidence:
            warnings.append(f"{len(low_confidence)} insights have low confidence")
        return warnings
