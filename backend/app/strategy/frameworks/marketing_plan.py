"""Marketing plan framework structure helpers — no decisions."""

from typing import Any


PLAN_KEYS = ("goals", "channels", "content", "metrics")

SECTION_HINTS = [
    "Executive Summary",
    "Market Analysis",
    "Strategy",
    "Goals",
    "Channels",
    "Content",
    "Metrics",
    "Recommendations",
    "Next Steps",
]


def empty_marketing_plan() -> dict[str, list[str]]:
    return {key: [] for key in PLAN_KEYS}


def normalize_marketing_plan(raw: dict[str, Any] | None) -> dict[str, list[str]]:
    base = empty_marketing_plan()
    if not raw:
        return base
    for key in PLAN_KEYS:
        items = raw.get(key) or []
        if isinstance(items, list):
            base[key] = [str(item) for item in items if str(item).strip()]
        elif isinstance(items, str) and items.strip():
            base[key] = [items.strip()]
    return base
