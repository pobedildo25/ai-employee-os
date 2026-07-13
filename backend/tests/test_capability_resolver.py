"""Unit tests for Capability Resolver ownership / ordering / fail-closed."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.skills.capability_resolver import (
    CAPABILITY_ORDER,
    apply_capability_order,
    build_required_capabilities,
    resolve_capability_graph,
)
from app.skills.registry import create_capability_registry
from app.skills.resolver import SkillResolverNode
from app.agent_runtime.state.models import create_initial_state


@pytest.fixture
def registry():
    return create_capability_registry(
        Settings(skills_enabled=True, research_enabled=True, research_allow_mock=True)
    )


def test_apply_capability_order_canonical() -> None:
    names = [
        "document_rendering",
        "document_analysis",
        "brand_style_analysis",
        "document_generation",
    ]
    ordered = apply_capability_order(names)
    assert ordered == [
        "document_analysis",
        "brand_style_analysis",
        "document_generation",
        "document_rendering",
    ]
    assert CAPABILITY_ORDER.index("research") < CAPABILITY_ORDER.index("strategy_analysis")
    assert CAPABILITY_ORDER.index("presentation_design") < CAPABILITY_ORDER.index(
        "document_rendering"
    )
    # L2: stub-only capabilities must not live in ORDER.
    assert "data_analysis" not in CAPABILITY_ORDER
    assert "content_analysis" not in CAPABILITY_ORDER


def test_research_before_strategy(registry) -> None:
    ordered = resolve_capability_graph(
        {"action": "EXECUTE"},
        {"required_capabilities": ["strategy_analysis", "research"]},
        registry,
    )
    assert ordered == ["research", "strategy_analysis"]


def test_presentation_before_render(registry) -> None:
    ordered = resolve_capability_graph(
        {"action": "EXECUTE"},
        {"required_capabilities": ["document_rendering", "presentation_design"]},
        registry,
    )
    assert ordered == ["presentation_design", "document_rendering"]


def test_drops_unknown_keeps_valid(registry) -> None:
    ordered = resolve_capability_graph(
        {"action": "EXECUTE"},
        {
            "required_capabilities": [
                "document_rendering",
                "unknown_capability",
                "document_generation",
            ]
        },
        registry,
    )
    assert ordered == ["document_generation", "document_rendering"]
    required = build_required_capabilities(
        {"action": "EXECUTE"},
        {
            "required_capabilities": [
                "document_rendering",
                "unknown_capability",
                "document_generation",
            ]
        },
        registry,
    )
    assert "unknown_capability" in required.unknown
    assert [c.name for c in required.resolved] == ordered


def test_empty_hints_uses_default_document_pipeline(registry) -> None:
    ordered = resolve_capability_graph(
        {"action": "EXECUTE"},
        {"required_capabilities": []},
        registry,
    )
    assert ordered == ["document_creation", "document_rendering"]


def test_all_unknown_falls_back_to_default_pipeline(registry) -> None:
    ordered = resolve_capability_graph(
        {"action": "EXECUTE"},
        {"required_capabilities": ["not_a_real_cap"]},
        registry,
    )
    assert ordered == ["document_creation", "document_rendering"]


def test_partial_hint_expands_render_dependency(registry) -> None:
    ordered = resolve_capability_graph(
        {"action": "EXECUTE"},
        {"required_capabilities": ["document_creation"]},
        registry,
    )
    assert ordered == ["document_creation", "document_rendering"]


def test_respond_returns_empty_without_error(registry) -> None:
    assert (
        resolve_capability_graph(
            {"action": "RESPOND"},
            {"required_capabilities": ["document_generation"]},
            registry,
        )
        == []
    )


def test_skill_resolver_node_reorders_and_owns_list(registry) -> None:
    node = SkillResolverNode(registry)
    state = create_initial_state(
        execution_id="exec-1",
        trace_id="trace-1",
        user_input="Create a document",
    )
    state["decision"] = {"action": "EXECUTE"}
    state["understanding"] = {
        "goal": "create document",
        "summary": "Need document generation",
        "required_capabilities": ["document_rendering", "document_generation"],
        "missing_information": [],
        "next_action": "execute",
    }

    update = node(state)
    assert update["status"] == "capabilities_resolved"
    assert update["understanding"]["required_capabilities"] == [
        "document_generation",
        "document_rendering",
    ]


def test_skill_resolver_node_empty_hints_defaults(registry) -> None:
    node = SkillResolverNode(registry)
    state = create_initial_state(
        execution_id="exec-1",
        trace_id="trace-1",
        user_input="do something",
    )
    state["decision"] = {"action": "EXECUTE"}
    state["understanding"] = {
        "goal": "unclear",
        "summary": "no caps",
        "required_capabilities": [],
        "missing_information": [],
        "next_action": "execute",
    }
    update = node(state)
    assert update["status"] == "capabilities_resolved"
    assert update["understanding"]["required_capabilities"] == [
        "document_creation",
        "document_rendering",
    ]
