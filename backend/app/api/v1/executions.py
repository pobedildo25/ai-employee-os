from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_orchestrator
from app.orchestration.orchestrator import Orchestrator
from app.orchestration.policies.execution_policy import can_cancel, can_pause, can_resume
from app.schemas.executions import (
    ExecutionControlResponse,
    ExecutionDetailResponse,
    ExecutionProgressResponse,
)

router = APIRouter(prefix="/executions", tags=["executions"])


@router.get("/{execution_id}", response_model=ExecutionDetailResponse)
async def get_execution(
    execution_id: str,
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> ExecutionDetailResponse:
    record = orchestrator.get_record(execution_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")

    state = record.state
    return ExecutionDetailResponse(
        execution_id=record.execution_id,
        trace_id=record.trace_id,
        status=state.control_status.value,
        progress=state.progress,
        execution_graph=record.graph.model_dump(mode="json"),
        execution_state=state.model_dump(mode="json"),
        task_plan=record.task_plan,
        task_execution=record.task_execution,
        active_nodes=list(state.current_nodes),
        completed_nodes=list(state.completed_nodes),
        failed_nodes=list(state.failed_nodes),
    )


@router.get("/{execution_id}/progress", response_model=ExecutionProgressResponse)
async def get_execution_progress(
    execution_id: str,
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> ExecutionProgressResponse:
    record = orchestrator.get_record(execution_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")

    return ExecutionProgressResponse(
        execution_id=record.execution_id,
        progress=record.state.progress,
        progress_percent=int(record.state.progress),
        telegram_progress=record.telegram_progress,
        execution_state=record.state,
    )


@router.post("/{execution_id}/pause", response_model=ExecutionControlResponse)
async def pause_execution(
    execution_id: str,
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> ExecutionControlResponse:
    record = orchestrator.get_record(execution_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    if not can_pause(record.state):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Execution cannot be paused")

    state = orchestrator.pause_execution(execution_id)
    if state is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pause failed")
    return ExecutionControlResponse(
        execution_id=execution_id,
        status=state.control_status.value,
        execution_state=state,
    )


@router.post("/{execution_id}/resume", response_model=ExecutionControlResponse)
async def resume_execution(
    execution_id: str,
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> ExecutionControlResponse:
    record = orchestrator.get_record(execution_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    if not can_resume(record.state):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Execution cannot be resumed")

    state = orchestrator.resume_execution(execution_id)
    if state is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resume failed")
    return ExecutionControlResponse(
        execution_id=execution_id,
        status=state.control_status.value,
        execution_state=state,
    )


@router.post("/{execution_id}/cancel", response_model=ExecutionControlResponse)
async def cancel_execution(
    execution_id: str,
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> ExecutionControlResponse:
    record = orchestrator.get_record(execution_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    if not can_cancel(record.state):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Execution cannot be cancelled")

    state = orchestrator.cancel_execution(execution_id)
    if state is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cancel failed")
    return ExecutionControlResponse(
        execution_id=execution_id,
        status=state.control_status.value,
        execution_state=state,
    )
