"""Competitor analysis framework structure helpers — no decisions."""

from typing import Any


SECTION_HINTS = [
    "Executive Summary",
    "Market Analysis",
    "Competitors",
    "Comparison",
    "Opportunities",
    "Recommendations",
    "Next Steps",
]


def empty_competitor_analysis() -> dict[str, Any]:
    return {
        "competitors": [],
        "comparison_points": [],
        "opportunities": [],
    }


def normalize_competitor_analysis(raw: dict[str, Any] | None) -> dict[str, Any]:
    base = empty_competitor_analysis()
    if not raw:
        return base
    competitors = raw.get("competitors") or []
    if isinstance(competitors, list):
        base["competitors"] = [str(item) for item in competitors if str(item).strip()]
    comparison = raw.get("comparison_points") or raw.get("comparison") or []
    if isinstance(comparison, list):
        base["comparison_points"] = [str(item) for item in comparison if str(item).strip()]
    opportunities = raw.get("opportunities") or []
    if isinstance(opportunities, list):
        base["opportunities"] = [str(item) for item in opportunities if str(item).strip()]
    return base
