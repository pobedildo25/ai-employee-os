import logging
from abc import ABC, abstractmethod
from typing import Any

from app.agent_runtime.state.models import AgentState

logger = logging.getLogger(__name__)


class BaseNode(ABC):
    """Base interface for LangGraph workflow nodes."""

    name: str

    @abstractmethod
    def __call__(self, state: AgentState) -> dict[str, Any]:
        """Receive state, apply changes, return partial state update."""

    def _log_node(self, state: AgentState, status: str) -> None:
        logger.info(
            "graph node execution | execution_id=%s trace_id=%s node_name=%s status=%s",
            state.get("execution_id", "-"),
            state.get("trace_id", "-"),
            self.name,
            status,
        )


class InputNode(BaseNode):
    """Demo node: normalizes user input into workflow state."""

    name = "process_input"

    def __call__(self, state: AgentState) -> dict[str, Any]:
        self._log_node(state, "started")
        user_input = state.get("user_input", "")
        messages = list(state.get("messages", []))
        if user_input:
            messages.append({"role": "user", "content": user_input})

        update = {
            "current_step": self.name,
            "messages": messages,
            "status": "processing",
        }
        self._log_node({**state, **update}, "completed")
        return update


class FinishNode(BaseNode):
    """Demo node: finalizes workflow execution."""

    name = "finish"

    def __call__(self, state: AgentState) -> dict[str, Any]:
        self._log_node(state, "started")
        update = {
            "current_step": self.name,
            "status": "completed",
            "result": {
                "understanding": state.get("understanding"),
                "decision": state.get("decision"),
                "processed": True,
            },
        }
        self._log_node({**state, **update}, "completed")
        return update
