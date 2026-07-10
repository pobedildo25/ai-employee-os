import copy
from abc import ABC, abstractmethod
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from app.agent_runtime.exceptions import CheckpointError
from app.agent_runtime.state.models import AgentState


class CheckpointManager(ABC):
    """Interface for saving and restoring workflow execution state."""

    @abstractmethod
    def save(self, execution_id: str, state: AgentState) -> None:
        """Persist workflow state for the given execution."""

    @abstractmethod
    def load(self, execution_id: str) -> AgentState | None:
        """Load persisted workflow state, or None if not found."""

    @abstractmethod
    def delete(self, execution_id: str) -> bool:
        """Remove persisted state. Returns True if an entry was removed."""

    @abstractmethod
    def get_checkpointer(self) -> Any:
        """Return LangGraph-compatible checkpointer instance."""


class InMemoryCheckpointManager(CheckpointManager):
    """In-memory checkpoint store for development and testing."""

    def __init__(self) -> None:
        self._store: dict[str, AgentState] = {}
        self._checkpointer = MemorySaver()

    def save(self, execution_id: str, state: AgentState) -> None:
        if not execution_id:
            raise CheckpointError("execution_id is required to save checkpoint")
        self._store[execution_id] = copy.deepcopy(state)

    def load(self, execution_id: str) -> AgentState | None:
        if not execution_id:
            raise CheckpointError("execution_id is required to load checkpoint")
        stored = self._store.get(execution_id)
        return copy.deepcopy(stored) if stored is not None else None

    def delete(self, execution_id: str) -> bool:
        if not execution_id:
            raise CheckpointError("execution_id is required to delete checkpoint")
        return self._store.pop(execution_id, None) is not None

    def get_checkpointer(self) -> MemorySaver:
        return self._checkpointer
