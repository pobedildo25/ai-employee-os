"""SWOT framework structure helpers — no decisions."""

from typing import Any


SWOT_KEYS = ("strengths", "weaknesses", "opportunities", "threats")

SECTION_HINTS = [
    "Executive Summary",
    "Strengths",
    "Weaknesses",
    "Opportunities",
    "Threats",
    "Recommendations",
    "Next Steps",
]


def empty_swot() -> dict[str, list[str]]:
    return {key: [] for key in SWOT_KEYS}


def normalize_swot(raw: dict[str, Any] | None) -> dict[str, list[str]]:
    base = empty_swot()
    if not raw:
        return base
    for key in SWOT_KEYS:
        items = raw.get(key) or []
        if isinstance(items, list):
            base[key] = [str(item) for item in items if str(item).strip()]
        elif isinstance(items, str) and items.strip():
            base[key] = [items.strip()]
    return base
