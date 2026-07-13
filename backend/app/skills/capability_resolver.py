"""Capability Resolver — owns the capability graph after Product Decision.

Executive may suggest ``required_capabilities`` as soft hints only.
This module validates hints against the registry, drops unknown/disabled,
applies canonical dependency ordering, and is the sole owner of the final
ordered list that enters Planner / direct_plan.

Fail-closed: empty result after filtering raises ``CapabilityResolutionError``.
No keyword routing from raw user text.
"""

from __future__ import annotations

from typing import Any

from app.agents.decision.policy import expects_capabilities, normalize_action
from app.agents.executive.models import AgentUnderstanding
from app.skills.models import Capability, RequiredCapabilities
from app.skills.registry import CapabilityRegistry


class CapabilityResolutionError(ValueError):
    """No usable capabilities resolved, or resolution policy violated."""


# Canonical pipeline order (index = priority). Unknown names sort after known ones.
CAPABILITY_ORDER: tuple[str, ...] = (
    "research",
    "document_analysis",
    "brand_style_analysis",
    "client_intelligence",
    "strategy_analysis",
    "analytics",
    "data_analysis",
    "content_analysis",
    "document_creation",
    "document_generation",
    "document_revision",
    "presentation_design",
    "document_rendering",
    "quality_review",
    "knowledge_migration",
)

# Explicit dependency edges (predecessor, successor) when both are present.
# Used to document policy; ordering is driven by CAPABILITY_ORDER.
CAPABILITY_DEPENDENCY_EDGES: tuple[tuple[str, str], ...] = (
    ("document_analysis", "brand_style_analysis"),
    ("brand_style_analysis", "document_generation"),
    ("brand_style_analysis", "document_creation"),
    ("document_generation", "document_rendering"),
    ("document_creation", "document_rendering"),
    ("research", "strategy_analysis"),
    ("strategy_analysis", "presentation_design"),
    ("presentation_design", "document_rendering"),
)

_ORDER_INDEX = {name: idx for idx, name in enumerate(CAPABILITY_ORDER)}


def apply_capability_order(names: list[str]) -> list[str]:
    """Reorder capability names by CAPABILITY_ORDER; stable for unknowns."""
    deduped: list[str] = []
    seen: set[str] = set()
    for name in names:
        if name not in seen:
            seen.add(name)
            deduped.append(name)

    known = [n for n in deduped if n in _ORDER_INDEX]
    unknown = [n for n in deduped if n not in _ORDER_INDEX]
    known.sort(key=lambda n: _ORDER_INDEX[n])
    return known + unknown


def _extract_hint(
    understanding: AgentUnderstanding | dict[str, Any] | None,
) -> list[str]:
    if understanding is None:
        return []
    if isinstance(understanding, AgentUnderstanding):
        raw = understanding.required_capabilities or []
    else:
        raw = understanding.get("required_capabilities") or []
    return [str(name).strip() for name in raw if name and str(name).strip()]


def resolve_capability_graph(
    decision: dict[str, Any] | None,
    understanding: AgentUnderstanding | dict[str, Any] | None,
    registry: CapabilityRegistry,
) -> list[str]:
    """Return ordered capability names owned by the Resolver.

    Ownership:
    - Executive hints are soft suggestions only.
    - Unknown / disabled capabilities are dropped (not fatal by themselves).
    - Remaining names are reordered by ``CAPABILITY_ORDER`` / dependency policy.
    - Empty result after filtering fails closed with a clear error.
    - No keyword routing from user text; no invented defaults from free text.
    """
    action = normalize_action((decision or {}).get("action"))
    if not expects_capabilities(action):
        return []

    hint = _extract_hint(understanding)
    if not hint:
        raise CapabilityResolutionError("no capabilities resolved")

    resolved = registry.find_capabilities(hint)
    available = {cap.name for cap in resolved}
    valid = [name for name in hint if name in available]
    if not valid:
        raise CapabilityResolutionError("no capabilities resolved")

    return apply_capability_order(valid)


def build_required_capabilities(
    decision: dict[str, Any] | None,
    understanding: AgentUnderstanding | dict[str, Any] | None,
    registry: CapabilityRegistry,
) -> RequiredCapabilities:
    """Validate hints and build RequiredCapabilities (raises when empty)."""
    requested = _extract_hint(understanding)
    ordered = resolve_capability_graph(decision, understanding, registry)
    resolved_caps: list[Capability] = registry.find_capabilities(ordered)
    dropped = [name for name in requested if name not in {c.name for c in resolved_caps}]
    return RequiredCapabilities(
        requested=requested,
        resolved=resolved_caps,
        unknown=dropped,
    )
