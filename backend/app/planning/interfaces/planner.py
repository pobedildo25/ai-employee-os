from abc import ABC, abstractmethod

from app.agents.executive.models import AgentUnderstanding
from app.context.models import ExecutionContext
from app.planning.models import TaskPlan
from app.skills.models import Capability


class TaskPlannerInterface(ABC):
    @abstractmethod
    async def create_plan(
        self,
        *,
        understanding: AgentUnderstanding,
        execution_context: ExecutionContext | dict,
        available_capabilities: list[Capability],
        trace_id: str = "-",
    ) -> TaskPlan:
        """Create a dynamic task plan."""
