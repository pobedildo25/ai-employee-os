"""Capability Resolver — owns the capability graph after Product Decision.

Executive may suggest ``required_capabilities`` as a temporary hint.
This module validates, filters, and orders the final list against the registry.
It does NOT invent capabilities from user text (keyword routing is forbidden).
"""

from __future__ import annotations

from typing import Any

from app.agents.decision.policy import expects_capabilities, normalize_action
from app.agents.executive.models import AgentUnderstanding
from app.skills.models import Capability, RequiredCapabilities
from app.skills.registry import CapabilityRegistry


class CapabilityResolutionError(ValueError):
    """Unknown or disabled capability requested for EXECUTE / CREATE_PLAN."""


def resolve_capability_graph(
    decision: dict[str, Any] | None,
    understanding: AgentUnderstanding | dict[str, Any] | None,
    registry: CapabilityRegistry,
) -> list[str]:
    """Return ordered capability names for the plan.

    Ownership:
    - Input list from Executive / understanding is a hint only.
    - Resolver validates against the registry and is the single owner of the
      ordered list that enters the TaskPlan.
    - Unknown or disabled capabilities raise ``CapabilityResolutionError``.
    - No keyword routing from user text.
    """
    action = normalize_action((decision or {}).get("action"))
    if not expects_capabilities(action):
        return []

    if understanding is None:
        hint: list[str] = []
    elif isinstance(understanding, AgentUnderstanding):
        hint = list(understanding.required_capabilities or [])
    else:
        hint = list(understanding.get("required_capabilities") or [])

    requested = [name.strip() for name in hint if name and str(name).strip()]
    if not requested:
        return []

    resolved = registry.find_capabilities(requested)
    resolved_by_name = {cap.name: cap for cap in resolved}
    ordered: list[str] = []
    unknown: list[str] = []
    for name in requested:
        if name in resolved_by_name:
            if name not in ordered:
                ordered.append(name)
        else:
            unknown.append(name)

    if unknown:
        raise CapabilityResolutionError(
            f"Unknown or disabled capabilities: {', '.join(unknown)}"
        )
    return ordered


def build_required_capabilities(
    decision: dict[str, Any] | None,
    understanding: AgentUnderstanding | dict[str, Any] | None,
    registry: CapabilityRegistry,
) -> RequiredCapabilities:
    """Validate hints and build RequiredCapabilities (raises on unknown/disabled)."""
    if understanding is None:
        requested: list[str] = []
    elif isinstance(understanding, AgentUnderstanding):
        requested = [n.strip() for n in understanding.required_capabilities if n and str(n).strip()]
    else:
        requested = [
            n.strip()
            for n in (understanding.get("required_capabilities") or [])
            if n and str(n).strip()
        ]

    ordered = resolve_capability_graph(decision, understanding, registry)
    resolved_caps: list[Capability] = registry.find_capabilities(ordered)
    return RequiredCapabilities(
        requested=requested,
        resolved=resolved_caps,
        unknown=[],
    )
