import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from app.agent_runtime.state.models import AgentState
from app.planning.executor import TaskExecutor
from app.planning.models import (
    ApprovalState,
    ApprovalStatus,
    TaskExecution,
    TaskExecutionStatus,
    TaskPlan,
)
from app.planning.policies.execution_policy import requires_approval
from app.skills.registry import CapabilityRegistry

logger = logging.getLogger(__name__)

EXECUTOR_NODE = "executor"
QUALITY_CHECK_NODE = "quality_check"


class QualityChecker(ABC):
    @abstractmethod
    async def check(
        self,
        plan: TaskPlan | None,
        execution: TaskExecution | None,
    ) -> dict[str, Any]:
        """Run quality check on execution results."""


class StubQualityChecker(QualityChecker):
    async def check(
        self,
        plan: TaskPlan | None,
        execution: TaskExecution | None,
    ) -> dict[str, Any]:
        if execution is None or execution.status != TaskExecutionStatus.COMPLETED:
            return {
                "passed": False,
                "score": 0.0,
                "notes": "No completed execution to check",
                "issues": [],
            }
        return {
            "passed": True,
            "score": 1.0,
            "notes": "Quality check stub — passed",
            "issues": [],
        }


class ExecutorNode:
    name = EXECUTOR_NODE

    def __init__(self, executor: TaskExecutor, registry: CapabilityRegistry) -> None:
        self._executor = executor
        self._registry = registry

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        _log_node(state, self.name, "started")
        plan_data = state.get("task_plan")
        decision = state.get("decision") or {}
        metadata = state.get("metadata") or {}

        if not plan_data:
            update = {
                "current_step": self.name,
                "status": "execution_skipped",
                "task_execution": None,
            }
            _log_node({**state, **update}, self.name, "skipped")
            return update

        plan = TaskPlan.model_validate(plan_data)

        if requires_approval(decision.get("action")) and not metadata.get("auto_approve"):
            execution = TaskExecution(
                plan_id=plan.id,
                status=TaskExecutionStatus.WAITING_APPROVAL,
                approval=ApprovalState(
                    status=ApprovalStatus.PENDING_APPROVAL,
                    requested_at=datetime.now(),
                ),
            )
            update = {
                "current_step": self.name,
                "task_execution": execution.model_dump(mode="json"),
                "status": "waiting_approval",
            }
            _log_node({**state, **update}, self.name, "waiting_approval")
            return update

        execution = await self._executor.execute(
            plan,
            self._registry,
            trace_id=state.get("trace_id", "-"),
        )
        update = {
            "current_step": self.name,
            "task_plan": plan.model_dump(mode="json"),
            "task_execution": execution.model_dump(mode="json"),
            "status": "executed"
            if execution.status == TaskExecutionStatus.COMPLETED
            else "execution_failed",
        }
        _log_node({**state, **update}, self.name, "completed")
        return update


class QualityCheckNode:
    name = QUALITY_CHECK_NODE

    def __init__(self, checker: QualityChecker | None = None) -> None:
        self._checker = checker or StubQualityChecker()

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        _log_node(state, self.name, "started")
        plan = TaskPlan.model_validate(state["task_plan"]) if state.get("task_plan") else None
        execution = (
            TaskExecution.model_validate(state["task_execution"])
            if state.get("task_execution")
            else None
        )

        quality_result = await self._checker.check(plan, execution)
        update = {
            "current_step": self.name,
            "quality_check": quality_result,
            "status": "completed",
            "result": {
                "execution_context": state.get("execution_context"),
                "understanding": state.get("understanding"),
                "decision": state.get("decision"),
                "required_capabilities": state.get("required_capabilities"),
                "task_plan": state.get("task_plan"),
                "task_execution": state.get("task_execution"),
                "quality_check": quality_result,
                "processed": True,
            },
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
