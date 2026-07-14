"""Capability Resolver — owns the capability graph after Product Decision.

Executive may suggest ``required_capabilities`` as soft hints only.
This module:
- treats hints as optional;
- applies default linear pipelines when hints are empty;
- expands known dependency edges;
- drops unknown/disabled names;
- applies canonical ordering.

Fail-closed only when no usable capability remains after defaults + filtering.
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
# Only enableable product capabilities (plus document_generation alias of document_creation).
# ``research`` is gated by research_enabled — kept here for ordering when registered.
CAPABILITY_ORDER: tuple[str, ...] = (
    "research",
    "document_analysis",
    "brand_style_analysis",
    "client_intelligence",
    "strategy_analysis",
    "analytics",
    "document_creation",
    "document_generation",  # alias exposed by DocumentCreationSkill
    "document_revision",
    "presentation_design",
    "document_rendering",
    "quality_review",
    "knowledge_migration",
)

# Explicit dependency edges (predecessor, successor) when both are present.
# Used for documentation / ordering context only — not auto-chained into plans.
CAPABILITY_DEPENDENCY_EDGES: tuple[tuple[str, str], ...] = (
    ("document_analysis", "brand_style_analysis"),
    ("brand_style_analysis", "document_generation"),
    ("brand_style_analysis", "document_creation"),
    ("document_generation", "document_rendering"),
    ("document_creation", "document_rendering"),
    ("research", "strategy_analysis"),
    ("strategy_analysis", "presentation_design"),
    ("presentation_design", "document_rendering"),
    ("document_revision", "document_rendering"),
)

# Only these edges are auto-completed for linear EXECUTE pipelines.
# Do NOT chain research→strategy→presentation (that is CREATE_PLAN territory).
RENDER_COMPLETION_EDGES: tuple[tuple[str, str], ...] = (
    ("document_generation", "document_rendering"),
    ("document_creation", "document_rendering"),
    ("presentation_design", "document_rendering"),
    ("document_revision", "document_rendering"),
)

# Default linear deliverable pipeline when Executive gives no capability hints.
DEFAULT_EXECUTE_PIPELINE: tuple[str, ...] = (
    "document_creation",
    "document_rendering",
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


def _available_names(registry: CapabilityRegistry, names: list[str] | tuple[str, ...]) -> list[str]:
    resolved = registry.find_capabilities(list(names))
    available = {cap.name for cap in resolved}
    return [name for name in names if name in available]


def _expand_dependencies(names: list[str], registry: CapabilityRegistry) -> list[str]:
    """Add registered render successors when a deliverable producer is present."""
    present = set(names)
    expanded = list(names)
    for predecessor, successor in RENDER_COMPLETION_EDGES:
        if predecessor not in present:
            continue
        if successor in present:
            continue
        if registry.get_skill_for_capability(successor) is None:
            continue
        expanded.append(successor)
        present.add(successor)
    return expanded


def _default_pipeline(registry: CapabilityRegistry) -> list[str]:
    return _available_names(registry, DEFAULT_EXECUTE_PIPELINE)


def resolve_capability_graph(
    decision: dict[str, Any] | None,
    understanding: AgentUnderstanding | dict[str, Any] | None,
    registry: CapabilityRegistry,
) -> list[str]:
    """Return ordered capability names owned by the Resolver.

    Ownership:
    - Executive hints are optional soft suggestions.
    - Empty hints → default linear document pipeline (if registered).
    - Non-empty hints that resolve to zero valid capabilities → fail closed.
    - Unknown / disabled capabilities are dropped from a mixed hint list.
    - Dependency edges complete partial pipelines.
    - Remaining names are reordered by ``CAPABILITY_ORDER``.
    - Empty result after defaults + filtering fails closed.
    - No keyword routing from user text.
    """
    action = normalize_action((decision or {}).get("action"))
    if not expects_capabilities(action):
        return []

    hint = _extract_hint(understanding)
    if hint:
        valid = _available_names(registry, hint)
        if not valid:
            raise CapabilityResolutionError(
                f"no valid capabilities for hints={hint!r}; refusing document pipeline fallback"
            )
        seed = valid
    else:
        seed = _default_pipeline(registry)

    if not seed:
        raise CapabilityResolutionError("no capabilities resolved")

    expanded = _expand_dependencies(seed, registry)
    ordered = apply_capability_order(expanded)
    if not ordered:
        raise CapabilityResolutionError("no capabilities resolved")
    return ordered


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
