import asyncio
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from app.orchestration.dependency_resolver import DependencyResolver
from app.orchestration.execution_graph import sync_node_from_plan_step
from app.orchestration.interfaces.orchestrator import OrchestratorInterface
from app.orchestration.models import (
    ExecutionControlStatus,
    ExecutionGraph,
    ExecutionGraphNode,
    ExecutionRecord,
    ExecutionState,
    NodeStatus,
)
from app.orchestration.policies.execution_policy import (
    can_cancel,
    can_pause,
    can_resume,
    should_continue_execution,
    should_fail_execution,
)
from app.orchestration.progress_tracker import ProgressTracker
from app.orchestration.scheduler import Scheduler
from app.orchestration.state_manager import StateManager
from app.orchestration.store import ExecutionStore, get_execution_store_singleton
from app.orchestration.validators.execution_validator import ExecutionValidator
from app.planning.executor import TaskExecutorError, _skill_result_succeeded
from app.planning.models import (
    ExecutionLogEntry,
    PlanStatus,
    PlanStep,
    StepStatus,
    TaskExecution,
    TaskExecutionStatus,
    TaskPlan,
)
from app.planning.policies.execution_policy import (
    MAX_STEP_RETRIES,
    is_critical_capability,
    is_retryable_failure,
    should_retry_step,
)
from app.skills.registry import CapabilityRegistry

logger = logging.getLogger(__name__)


class Orchestrator(OrchestratorInterface):
    def __init__(
        self,
        *,
        store: ExecutionStore | None = None,
        resolver: DependencyResolver | None = None,
        scheduler: Scheduler | None = None,
        state_manager: StateManager | None = None,
        progress_tracker: ProgressTracker | None = None,
        validator: ExecutionValidator | None = None,
    ) -> None:
        self._store = store or get_execution_store_singleton()
        self._resolver = resolver or DependencyResolver()
        self._scheduler = scheduler or Scheduler()
        self._state_manager = state_manager or StateManager()
        self._progress = progress_tracker or ProgressTracker()
        self._validator = validator or ExecutionValidator()

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
        self._validator.validate_graph(graph)
        context = execution_context or {}

        execution = TaskExecution(
            task_id=plan.id,
            plan_id=plan.id,
            status=TaskExecutionStatus.RUNNING,
            logs=[ExecutionLogEntry(message=f"Orchestrated execution started for plan {plan.id}")],
        )
        plan.status = PlanStatus.READY

        self._persist_record(
            execution_state.execution_id,
            graph,
            execution_state,
            plan,
            execution,
            trace_id=trace_id,
        )

        while should_continue_execution(execution_state, graph):
            if self._state_manager.is_paused(execution_state):
                await asyncio.sleep(0.05)
                record = self._store.get(execution_state.execution_id)
                if record is not None:
                    execution_state = record.state
                continue

            if self._state_manager.is_cancelled(execution_state):
                self._scheduler.mark_cancelled(graph)
                execution.status = TaskExecutionStatus.CANCELLED
                execution.logs.append(ExecutionLogEntry(message="Execution cancelled"))
                break

            ready_nodes = self._resolver.get_ready_nodes(graph)
            if not ready_nodes:
                if self._resolver.is_complete(graph):
                    break
                await asyncio.sleep(0.01)
                continue

            running_ids = self._scheduler.mark_running(graph, ready_nodes)
            execution_state = self._state_manager.refresh(execution_state, graph)
            execution_state.progress = self._progress.calculate_progress(graph)
            self._sync_store(execution_state, graph, plan, execution, trace_id)

            await asyncio.gather(
                *[
                    self._run_node(
                        graph=graph,
                        plan=plan,
                        node_id=node_id,
                        registry=registry,
                        execution=execution,
                        execution_context=context,
                        trace_id=trace_id,
                    )
                    for node_id in running_ids
                ]
            )

            execution_state = self._state_manager.refresh(execution_state, graph)
            execution_state.progress = self._progress.calculate_progress(graph)
            self._sync_store(execution_state, graph, plan, execution, trace_id)

        if execution_state.control_status == ExecutionControlStatus.CANCELLED:
            execution.status = TaskExecutionStatus.CANCELLED
        elif should_fail_execution(execution_state, graph):
            plan.status = PlanStatus.FAILED
            execution.status = TaskExecutionStatus.FAILED
            failed = graph.nodes[execution_state.failed_nodes[0]] if execution_state.failed_nodes else None
            reason = failed.error if failed else "One or more steps failed"
            execution_state = self._state_manager.fail(execution_state, reason)
            execution.logs.append(ExecutionLogEntry(level="error", message=reason))
        else:
            plan.status = PlanStatus.COMPLETED
            execution.status = TaskExecutionStatus.COMPLETED
            execution_state = self._state_manager.complete(execution_state)

        execution.current_step = None
        execution.results = {
            "goal": plan.goal,
            "summary": plan.summary,
            "steps_completed": len([s for s in plan.steps if s.status == StepStatus.COMPLETED]),
            "steps_failed": len([s for s in plan.steps if s.status == StepStatus.FAILED]),
            "progress": execution_state.progress,
        }
        execution_state.progress = self._progress.calculate_progress(graph)
        self._sync_store(execution_state, graph, plan, execution, trace_id)
        return execution_state, execution

    async def _run_node(
        self,
        *,
        graph: ExecutionGraph,
        plan: TaskPlan,
        node_id: str,
        registry: CapabilityRegistry,
        execution: TaskExecution,
        execution_context: dict[str, Any],
        trace_id: str,
    ) -> None:
        node = graph.nodes[node_id]
        step = _find_plan_step(plan, node.id)
        if step is None:
            self._scheduler.mark_failed(graph, node_id, f"Plan step not found for node {node_id}")
            return

        execution.current_step = step.id
        step.status = StepStatus.RUNNING
        execution.logs.append(
            ExecutionLogEntry(step_id=step.id, message=f"Step started: {step.description}")
        )

        success = await self._run_step_with_retry(
            step=step,
            node=node,
            graph=graph,
            plan=plan,
            registry=registry,
            execution=execution,
            execution_context=execution_context,
            trace_id=trace_id,
        )

        if success:
            self._scheduler.mark_completed(graph, node_id, step.result)
            sync_node_from_plan_step(graph, step.id, status=NodeStatus.COMPLETED, result=step.result)
        else:
            error = node.error or f"Step failed: {step.description}"
            self._scheduler.mark_failed(graph, node_id, error)
            sync_node_from_plan_step(graph, step.id, status=NodeStatus.FAILED, error=error)

    async def _run_step_with_retry(
        self,
        *,
        step: PlanStep,
        node: ExecutionGraphNode,
        graph: ExecutionGraph,
        plan: TaskPlan,
        registry: CapabilityRegistry,
        execution: TaskExecution,
        execution_context: dict[str, Any],
        trace_id: str,
    ) -> bool:
        for attempt in range(1, MAX_STEP_RETRIES + 1):
            try:
                result = await self._execute_step(step, registry, execution_context, trace_id, plan)
                if not _skill_result_succeeded(result):
                    status = result.get("status") if isinstance(result, dict) else None
                    step.status = StepStatus.FAILED
                    step.result = result
                    node.error = f"skill returned status={status!r}"
                    node.retry_count = attempt
                    execution.logs.append(
                        ExecutionLogEntry(
                            step_id=step.id,
                            level="error",
                            message=(
                                f"Step failed (attempt {attempt}): "
                                f"skill returned status={status!r}"
                            ),
                        )
                    )
                    logger.warning(
                        "orchestration step incomplete | trace_id=%s step_id=%s attempt=%d status=%s",
                        trace_id,
                        step.id,
                        attempt,
                        status,
                    )
                    if not is_retryable_failure(status) or not should_retry_step(step, attempt):
                        if self._giveup_is_tolerable(step, node, execution, trace_id, registry):
                            return True
                        return False
                    step.status = StepStatus.PENDING
                    continue
                step.status = StepStatus.COMPLETED
                step.result = result
                node.retry_count = attempt
                execution.logs.append(
                    ExecutionLogEntry(step_id=step.id, message=f"Step completed: {step.description}")
                )
                return True
            except Exception as exc:
                step.status = StepStatus.FAILED
                node.error = str(exc)
                node.retry_count = attempt
                execution.logs.append(
                    ExecutionLogEntry(
                        step_id=step.id,
                        level="error",
                        message=f"Step failed (attempt {attempt}): {exc}",
                    )
                )
                logger.warning(
                    "orchestration step failed | trace_id=%s step_id=%s attempt=%d error=%s",
                    trace_id,
                    step.id,
                    attempt,
                    exc,
                )
                if not should_retry_step(step, attempt):
                    if self._giveup_is_tolerable(step, node, execution, trace_id, registry):
                        return True
                    return False
                step.status = StepStatus.PENDING
        return False

    @staticmethod
    def _giveup_is_tolerable(
        step: PlanStep,
        node: ExecutionGraphNode,
        execution: TaskExecution,
        trace_id: str,
        registry: CapabilityRegistry | None = None,
    ) -> bool:
        """Non-critical enrichment steps degrade to skipped instead of failing the task."""
        if is_critical_capability(step.capability, registry):
            return False
        reason = node.error or "enrichment unavailable"
        step.status = StepStatus.COMPLETED
        step.result = {"status": "skipped", "skill": step.capability, "reason": reason}
        node.error = None
        execution.logs.append(
            ExecutionLogEntry(
                step_id=step.id,
                message=f"Enrichment step skipped (best-effort): {step.capability} — {reason}",
            )
        )
        logger.warning(
            "orchestration enrichment skipped | trace_id=%s step_id=%s capability=%s reason=%s",
            trace_id,
            step.id,
            step.capability,
            reason,
        )
        return True

    async def _execute_step(
        self,
        step: PlanStep,
        registry: CapabilityRegistry,
        execution_context: dict[str, Any],
        trace_id: str,
        plan: TaskPlan,
    ) -> dict[str, Any]:
        skill = registry.get_skill_for_capability(step.capability)
        if skill is None:
            raise TaskExecutorError(f"No skill registered for capability: {step.capability}")

        payload = {
            "step_id": str(step.id),
            "description": step.description,
            "capability": step.capability,
            "goal": execution_context.get("user_goal") or execution_context.get("user_input"),
            "user_goal": execution_context.get("user_goal") or execution_context.get("user_input"),
            "context": execution_context,
            "trace_id": trace_id,
            **execution_context,
        }
        payload = self._merge_attachment_fields(execution_context, payload)
        payload = self._enrich_payload_from_plan(step, plan, payload)
        return await skill.execute(payload)

    def _merge_attachment_fields(
        self,
        execution_context: dict[str, Any],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        attachment_keys = (
            "extracted_content",
            "file_bytes",
            "filename",
            "brand_profile",
            "agency_profile",
            "agency_context",
            "artifact_id",
            "client_id",
            "project_id",
        )
        sources = (
            execution_context,
            execution_context.get("metadata") or {},
            execution_context.get("extensions") or {},
        )
        for source in sources:
            if not isinstance(source, dict):
                continue
            for key in attachment_keys:
                if key not in payload and source.get(key) is not None:
                    payload[key] = source[key]
        return payload

    def _enrich_payload_from_plan(
        self,
        step: PlanStep,
        plan: TaskPlan,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        completed = {
            item.id: item
            for item in plan.steps
            if item.status == StepStatus.COMPLETED and item.result
        }
        merge_keys = (
            "document_ast",
            "brand_profile",
            "extracted_content",
            "representation",
            "document_representation",
            "research_result",
            "strategy_result",
            "presentation_plan",
            "render_result",
            "file_bytes",
            "filename",
            "artifact_id",
            "source_artifact_id",
            "knowledge_result",
            "client_intelligence_result",
            "analytics_result",
            "learning_rules",
        )

        for dep_id in step.dependencies:
            dep_step = completed.get(dep_id)
            if dep_step is None or not dep_step.result:
                continue
            result = dep_step.result
            for key in merge_keys:
                if key in result and result[key] is not None:
                    payload[key] = result[key]
            if "representation" in result and payload.get("document_representation") is None:
                payload["document_representation"] = result["representation"]
            # Generic metadata from prior steps (skills own format/store defaults).
            dep_meta = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
            if dep_meta.get("document_type") and not payload.get("output_format"):
                payload["output_format"] = dep_meta["document_type"]
            if dep_meta.get("output_format") and not payload.get("output_format"):
                payload["output_format"] = dep_meta["output_format"]
            if "store_artifact" in dep_meta and "store_artifact" not in payload:
                payload["store_artifact"] = dep_meta["store_artifact"]

        return payload

    def pause_execution(self, execution_id: str) -> ExecutionState | None:
        record = self._store.get(execution_id)
        if record is None or not can_pause(record.state):
            return None
        record.state = self._state_manager.pause(record.state)
        self._scheduler.mark_paused(record.graph)
        record.state = self._state_manager.refresh(record.state, record.graph)
        record.state.progress = self._progress.calculate_progress(record.graph)
        record.telegram_progress = self._progress.build_telegram_progress(
            execution_id,
            record.graph,
            progress=record.state.progress,
        )
        self._store.save(record)
        return record.state

    def resume_execution(self, execution_id: str) -> ExecutionState | None:
        record = self._store.get(execution_id)
        if record is None or not can_resume(record.state):
            return None
        self._scheduler.resume_paused(record.graph)
        record.state = self._state_manager.resume(record.state)
        record.state = self._state_manager.refresh(record.state, record.graph)
        record.state.progress = self._progress.calculate_progress(record.graph)
        record.telegram_progress = self._progress.build_telegram_progress(
            execution_id,
            record.graph,
            progress=record.state.progress,
        )
        self._store.save(record)
        return record.state

    def cancel_execution(self, execution_id: str) -> ExecutionState | None:
        record = self._store.get(execution_id)
        if record is None or not can_cancel(record.state):
            return None
        self._scheduler.mark_cancelled(record.graph)
        record.state = self._state_manager.cancel(record.state, reason="Cancelled by user")
        record.state = self._state_manager.refresh(record.state, record.graph)
        record.state.progress = self._progress.calculate_progress(record.graph)
        record.telegram_progress = self._progress.build_telegram_progress(
            execution_id,
            record.graph,
            progress=record.state.progress,
        )
        self._store.save(record)
        return record.state

    def get_record(self, execution_id: str) -> ExecutionRecord | None:
        return self._store.get(execution_id)

    def _persist_record(
        self,
        execution_id: str,
        graph: ExecutionGraph,
        state: ExecutionState,
        plan: TaskPlan,
        execution: TaskExecution,
        *,
        trace_id: str,
    ) -> None:
        record = ExecutionRecord(
            execution_id=execution_id,
            trace_id=trace_id,
            graph=graph,
            state=state,
            task_plan=plan.model_dump(mode="json"),
            task_execution=execution.model_dump(mode="json"),
            telegram_progress=self._progress.build_telegram_progress(execution_id, graph, progress=state.progress),
        )
        self._store.save(record)

    def _sync_store(
        self,
        state: ExecutionState,
        graph: ExecutionGraph,
        plan: TaskPlan,
        execution: TaskExecution,
        trace_id: str,
    ) -> None:
        record = self._store.get(state.execution_id)
        if record is None:
            self._persist_record(state.execution_id, graph, state, plan, execution, trace_id=trace_id)
            return
        record.graph = graph
        record.state = state
        record.task_plan = plan.model_dump(mode="json")
        record.task_execution = execution.model_dump(mode="json")
        record.telegram_progress = self._progress.build_telegram_progress(
            state.execution_id,
            graph,
            progress=state.progress,
        )
        self._store.save(record)


def _find_plan_step(plan: TaskPlan, step_id: UUID) -> PlanStep | None:
    for step in plan.steps:
        if step.id == step_id:
            return step
    return None
