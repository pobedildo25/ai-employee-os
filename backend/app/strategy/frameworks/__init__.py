from app.strategy.frameworks import competitor_analysis, marketing_plan, positioning, swot
from app.strategy.models import StrategyType

FRAMEWORK_HINTS: dict[StrategyType, list[str]] = {
    StrategyType.SWOT_ANALYSIS: swot.SECTION_HINTS,
    StrategyType.POSITIONING: positioning.SECTION_HINTS,
    StrategyType.MARKETING_STRATEGY: marketing_plan.SECTION_HINTS,
    StrategyType.GO_TO_MARKET: marketing_plan.SECTION_HINTS,
    StrategyType.CAMPAIGN_PLAN: marketing_plan.SECTION_HINTS,
    StrategyType.COMPETITOR_ANALYSIS: competitor_analysis.SECTION_HINTS,
}


def section_hints_for(strategy_type: StrategyType | str | None) -> list[str]:
    if strategy_type is None:
        return [
            "Executive Summary",
            "Market Analysis",
            "Strategy",
            "Recommendations",
            "Next Steps",
        ]
    if isinstance(strategy_type, str):
        try:
            strategy_type = StrategyType(strategy_type.lower())
        except ValueError:
            return FRAMEWORK_HINTS[StrategyType.MARKETING_STRATEGY]
    return FRAMEWORK_HINTS.get(strategy_type, FRAMEWORK_HINTS[StrategyType.MARKETING_STRATEGY])


def normalize_framework(strategy_type: StrategyType, raw: dict | None) -> dict:
    if strategy_type == StrategyType.SWOT_ANALYSIS:
        return swot.normalize_swot(raw)
    if strategy_type == StrategyType.POSITIONING:
        return positioning.normalize_positioning(raw)
    if strategy_type == StrategyType.COMPETITOR_ANALYSIS:
        return competitor_analysis.normalize_competitor_analysis(raw)
    return marketing_plan.normalize_marketing_plan(raw)
