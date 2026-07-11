from abc import ABC, abstractmethod
from typing import Any

from app.orchestration.models import ExecutionGraph, ExecutionState
from app.planning.models import TaskExecution, TaskPlan
from app.skills.registry import CapabilityRegistry


class OrchestratorInterface(ABC):
    @abstractmethod
    async def execute(
        self,
        graph: ExecutionGraph,
        plan: TaskPlan,
        registry: CapabilityRegistry,
        execution_state: ExecutionState,
        *,
        execution_context: dict[str, Any] | None = None,
        trace_id: str = "-",
    ) -> tuple[ExecutionState, TaskExecution]:
        """Execute an ExecutionGraph and return updated state and task execution."""

    @abstractmethod
    def pause_execution(self, execution_id: str) -> ExecutionState | None:
        """Pause a running execution."""

    @abstractmethod
    def resume_execution(self, execution_id: str) -> ExecutionState | None:
        """Resume a paused execution."""

    @abstractmethod
    def cancel_execution(self, execution_id: str) -> ExecutionState | None:
        """Cancel a running or paused execution."""
