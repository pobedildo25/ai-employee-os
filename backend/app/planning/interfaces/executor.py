from abc import ABC, abstractmethod
from uuid import UUID

from app.planning.models import TaskExecution, TaskPlan
from app.skills.registry import CapabilityRegistry


class TaskExecutorInterface(ABC):
    @abstractmethod
    async def execute(
        self,
        plan: TaskPlan,
        registry: CapabilityRegistry,
        *,
        task_id: UUID | None = None,
        trace_id: str = "-",
    ) -> TaskExecution:
        """Execute plan steps via registered skills."""
