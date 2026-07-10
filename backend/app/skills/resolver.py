import logging
from typing import Any

from app.agent_runtime.state.models import AgentState
from app.agents.executive.models import AgentUnderstanding
from app.skills.models import RequiredCapabilities
from app.skills.registry import CapabilityRegistry

logger = logging.getLogger(__name__)

SKILL_RESOLVER_NODE = "skill_resolver"


class SkillResolverNode:
    """Resolves AgentUnderstanding.required_capabilities against the registry."""

    name = SKILL_RESOLVER_NODE

    def __init__(self, registry: CapabilityRegistry) -> None:
        self._registry = registry

    def __call__(self, state: AgentState) -> dict[str, Any]:
        _log_node(state, self.name, "started")
        understanding_data = state.get("understanding") or {}
        understanding = AgentUnderstanding.model_validate(understanding_data)
        requested = understanding.required_capabilities

        resolved = self._registry.find_capabilities(requested)
        resolved_names = {capability.name for capability in resolved}
        unknown = [name for name in requested if name not in resolved_names]

        required = RequiredCapabilities(
            requested=requested,
            resolved=resolved,
            unknown=unknown,
        )

        update = {
            "current_step": self.name,
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
