import copy
import logging
import pickle
from abc import ABC, abstractmethod
from typing import Any

import redis
from langgraph.checkpoint.memory import MemorySaver

from app.agent_runtime.exceptions import CheckpointError
from app.agent_runtime.state.models import AgentState
from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

_CHECKPOINT_KEY_PREFIX = "agent:checkpoint:"


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


class RedisCheckpointManager(CheckpointManager):
    """Persist AgentRuntime final-state blobs in Redis (app-level checkpoint).

    LangGraph interrupt checkpointer remains MemorySaver — ``langgraph.checkpoint.redis``
    is not in project deps. Production uses Redis for durable execution_id → state;
    tests/dev keep InMemoryCheckpointManager.
    """

    def __init__(
        self,
        redis_url: str,
        *,
        ttl_seconds: int = 604800,
        client: redis.Redis | None = None,
    ) -> None:
        self._ttl_seconds = max(1, int(ttl_seconds))
        self._client = client or redis.from_url(redis_url, decode_responses=False)
        self._checkpointer = MemorySaver()

    def _key(self, execution_id: str) -> str:
        return f"{_CHECKPOINT_KEY_PREFIX}{execution_id}"

    def save(self, execution_id: str, state: AgentState) -> None:
        if not execution_id:
            raise CheckpointError("execution_id is required to save checkpoint")
        try:
            payload = pickle.dumps(dict(state), protocol=pickle.HIGHEST_PROTOCOL)
            self._client.set(self._key(execution_id), payload, ex=self._ttl_seconds)
        except Exception as exc:
            raise CheckpointError(f"Failed to save checkpoint: {exc}") from exc

    def load(self, execution_id: str) -> AgentState | None:
        if not execution_id:
            raise CheckpointError("execution_id is required to load checkpoint")
        try:
            raw = self._client.get(self._key(execution_id))
        except Exception as exc:
            raise CheckpointError(f"Failed to load checkpoint: {exc}") from exc
        if raw is None:
            return None
        try:
            data = pickle.loads(raw)
        except Exception as exc:
            raise CheckpointError(f"Failed to decode checkpoint: {exc}") from exc
        if not isinstance(data, dict):
            raise CheckpointError("Checkpoint payload is not a state dict")
        return copy.deepcopy(data)

    def delete(self, execution_id: str) -> bool:
        if not execution_id:
            raise CheckpointError("execution_id is required to delete checkpoint")
        try:
            return bool(self._client.delete(self._key(execution_id)))
        except Exception as exc:
            raise CheckpointError(f"Failed to delete checkpoint: {exc}") from exc

    def get_checkpointer(self) -> MemorySaver:
        return self._checkpointer


def create_checkpoint_manager(settings: Settings | None = None) -> CheckpointManager:
    """Production → RedisCheckpointManager; otherwise InMemory (tests/dev)."""
    cfg = settings or get_settings()
    if cfg.is_production:
        logger.info(
            "using RedisCheckpointManager | ttl_seconds=%s",
            cfg.checkpoint_ttl_seconds,
        )
        return RedisCheckpointManager(
            cfg.redis_url,
            ttl_seconds=cfg.checkpoint_ttl_seconds,
        )
    return InMemoryCheckpointManager()
