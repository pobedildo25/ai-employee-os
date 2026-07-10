import logging
from typing import Any

from app.agent_runtime.graph.nodes import BaseNode
from app.agent_runtime.state.models import AgentState
from app.agents.executive.agent import ExecutiveAgent

logger = logging.getLogger(__name__)

EXECUTIVE_AGENT_NODE = "executive_agent"
DECISION_NODE = "decision"


class ExecutiveAgentNode:
    """LangGraph node: runs executive agent analysis via LLM Gateway."""

    name = EXECUTIVE_AGENT_NODE

    def __init__(self, agent: ExecutiveAgent) -> None:
        self._agent = agent

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        _log_node(state, self.name, "started")
        result = await self._agent.analyze(state)
        update = {
            "current_step": self.name,
            "understanding": result.understanding.model_dump(),
            "decision": result.decision.model_dump(),
            "status": "analyzed",
        }
        _log_node({**state, **update}, self.name, "completed")
        return update


class DecisionNode(BaseNode):
    """Records the executive decision in workflow state without business routing."""

    name = DECISION_NODE

    def __call__(self, state: AgentState) -> dict[str, Any]:
        self._log_node(state, "started")
        decision = state.get("decision") or {}
        update = {
            "current_step": self.name,
            "status": "decided",
            "metadata": {
                **(state.get("metadata") or {}),
                "decision_action": decision.get("action"),
            },
        }
        self._log_node({**state, **update}, "completed")
        return update


def _log_node(state: AgentState, node_name: str, status: str) -> None:
    logger.info(
        "graph node execution | execution_id=%s trace_id=%s node_name=%s status=%s",
        state.get("execution_id", "-"),
        state.get("trace_id", "-"),
        node_name,
        status,
    )
