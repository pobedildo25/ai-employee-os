"""Positioning framework structure helpers — no decisions."""

from typing import Any


POSITIONING_KEYS = ("audience", "problem", "solution", "differentiation")

SECTION_HINTS = [
    "Executive Summary",
    "Audience",
    "Problem",
    "Solution",
    "Differentiation",
    "Recommendations",
    "Next Steps",
]


def empty_positioning() -> dict[str, str]:
    return {key: "" for key in POSITIONING_KEYS}


def normalize_positioning(raw: dict[str, Any] | None) -> dict[str, str]:
    base = empty_positioning()
    if not raw:
        return base
    for key in POSITIONING_KEYS:
        value = raw.get(key)
        if value is not None:
            base[key] = str(value).strip()
    return base
