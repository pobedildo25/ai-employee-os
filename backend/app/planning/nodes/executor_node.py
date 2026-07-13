import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from app.agent_runtime.state.models import AgentState
from app.orchestration.models import ExecutionGraph, ExecutionState
from app.orchestration.orchestrator import Orchestrator
from app.orchestration.progress_tracker import ProgressTracker
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
        if execution is not None and execution.status == TaskExecutionStatus.COMPLETED:
            return {
                "passed": True,
                "score": 1.0,
                "notes": "Quality check stub — passed",
                "issues": [],
            }
        return {
            "passed": False,
            "score": 0.0,
            "notes": "No completed execution to check",
            "issues": [],
        }


class ExecutorNode:
    name = EXECUTOR_NODE

    def __init__(
        self,
        executor: TaskExecutor,
        registry: CapabilityRegistry,
        orchestrator: Orchestrator | None = None,
    ) -> None:
        self._executor = executor
        self._registry = registry
        self._orchestrator = orchestrator or Orchestrator()
        self._progress = ProgressTracker()

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

        if requires_approval(decision.get("action"), plan) and not metadata.get("auto_approve"):
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

        graph_data = state.get("execution_graph")
        state_data = state.get("execution_state")

        if graph_data and state_data:
            graph = ExecutionGraph.model_validate(graph_data)
            execution_state = ExecutionState.model_validate(state_data)
            execution_state, execution = await self._orchestrator.execute(
                graph,
                plan,
                self._registry,
                execution_state,
                execution_context=state.get("execution_context") or {},
                trace_id=state.get("trace_id", "-"),
            )
            telegram_progress = self._progress.build_telegram_progress(
                state.get("execution_id", ""),
                graph,
                progress=execution_state.progress,
            )
            skill_updates = _merge_skill_results(plan)
            update = {
                "current_step": self.name,
                "task_plan": plan.model_dump(mode="json"),
                "task_execution": execution.model_dump(mode="json"),
                "execution_graph": graph.model_dump(mode="json"),
                "execution_state": execution_state.model_dump(mode="json"),
                "progress": execution_state.progress,
                "active_nodes": list(execution_state.current_nodes),
                "completed_nodes": list(execution_state.completed_nodes),
                "failed_nodes": list(execution_state.failed_nodes),
                "telegram_progress": telegram_progress.model_dump(mode="json"),
                "status": "executed"
                if execution.status == TaskExecutionStatus.COMPLETED
                else "execution_failed",
                **skill_updates,
            }
        else:
            execution = await self._executor.execute(
                plan,
                self._registry,
                trace_id=state.get("trace_id", "-"),
                execution_context=state.get("execution_context") or {},
            )
            skill_updates = _merge_skill_results(plan)
            completed = execution.status == TaskExecutionStatus.COMPLETED
            update = {
                "current_step": self.name,
                "task_plan": plan.model_dump(mode="json"),
                "task_execution": execution.model_dump(mode="json"),
                "progress": 100.0 if completed else 0.0,
                "status": "executed" if completed else "execution_failed",
                **skill_updates,
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
        decision_action = (state.get("decision") or {}).get("action")
        if decision_action in {"RESPOND", "ASK_CLARIFICATION"}:
            quality_result = {
                "passed": True,
                "score": 1.0,
                "notes": "Non-document flow completed",
                "issues": [],
            }
        elif state.get("render_result") or state.get("document_ast"):
            quality_result = {
                "passed": True,
                "score": 1.0,
                "notes": "Document pipeline completed",
                "issues": [],
            }
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
                "document_creation_result": state.get("document_creation_result"),
                "document_ast": state.get("document_ast"),
                "render_result": state.get("render_result"),
                "quality_check": quality_result,
                "processed": True,
            },
        }
        _log_node({**state, **update}, self.name, "completed")
        return update


def _merge_skill_results(plan: TaskPlan) -> dict[str, object]:
    updates: dict[str, object] = {}
    for step in plan.steps:
        if not step.result:
            continue
        if step.result.get("document_ast"):
            updates["document_ast"] = step.result["document_ast"]
        if step.result.get("document_creation_result"):
            updates["document_creation_result"] = step.result["document_creation_result"]
        if step.result.get("render_result"):
            updates["render_result"] = step.result["render_result"]
        if step.result.get("research_result"):
            updates["research_result"] = step.result["research_result"]
        if step.result.get("strategy_result"):
            updates["strategy_result"] = step.result["strategy_result"]
        if step.result.get("presentation_plan"):
            updates["presentation_plan"] = step.result["presentation_plan"]
        if step.result.get("analytics_result"):
            updates["analytics_result"] = step.result["analytics_result"]
        if step.result.get("client_intelligence_result"):
            updates["client_intelligence_result"] = step.result["client_intelligence_result"]
    return updates


def _log_node(state: AgentState, node_name: str, status: str) -> None:
    logger.info(
        "graph node execution | execution_id=%s trace_id=%s node_name=%s status=%s",
        state.get("execution_id", "-"),
        state.get("trace_id", "-"),
        node_name,
        status,
    )
