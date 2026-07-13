import logging
from typing import Any

from app.agent_runtime.state.models import AgentState
from app.agents.executive.models import AgentUnderstanding
from app.skills.capability_resolver import (
    CapabilityResolutionError,
    build_required_capabilities,
    resolve_capability_graph,
)
from app.skills.registry import CapabilityRegistry

logger = logging.getLogger(__name__)

SKILL_RESOLVER_NODE = "skill_resolver"


class SkillResolverNode:
    """Owns final capability list: validates Executive hints against the registry."""

    name = SKILL_RESOLVER_NODE

    def __init__(self, registry: CapabilityRegistry) -> None:
        self._registry = registry

    def __call__(self, state: AgentState) -> dict[str, Any]:
        _log_node(state, self.name, "started")
        understanding_data = state.get("understanding") or {}
        understanding = AgentUnderstanding.model_validate(understanding_data)
        decision = state.get("decision") or {}

        try:
            ordered = resolve_capability_graph(decision, understanding, self._registry)
            required = build_required_capabilities(decision, understanding, self._registry)
        except CapabilityResolutionError as exc:
            update = {
                "current_step": self.name,
                "required_capabilities": {
                    "requested": list(understanding.required_capabilities),
                    "resolved": [],
                    "unknown": [str(exc)],
                },
                "status": "capabilities_failed",
                "error": str(exc),
            }
            _log_node({**state, **update}, self.name, "failed")
            return update

        # Resolver owns the ordered list that enters the plan / understanding.
        updated_understanding = understanding.model_copy(
            update={"required_capabilities": ordered}
        ).model_dump(mode="json")

        update = {
            "current_step": self.name,
            "understanding": updated_understanding,
            "required_capabilities": required.model_dump(),
            "status": "capabilities_resolved",
        }
        _log_node({**state, **update}, self.name, "completed")
        return update


def _log_node(state: AgentState, node_name: str, status: str) -> None:
    logger.info(
        "graph node execution | execution_id=%s trace_id=%s node_name=%s status=%s",
        state.get("execution_id", "-"),
        state.get("trace_id", "-"),
        node_name,
        status,
    )
