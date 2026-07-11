from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_observability_manager
from app.observability.manager import ObservabilityManager
from app.observability.models import ExecutionTrace, MetricsSnapshot

router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/traces", response_model=list[ExecutionTrace])
async def list_traces(
    limit: int = Query(default=100, ge=1, le=500),
    manager: ObservabilityManager = Depends(get_observability_manager),
) -> list[ExecutionTrace]:
    return await manager.list_traces(limit=limit)


@router.get("/traces/{trace_id}", response_model=ExecutionTrace)
async def get_trace(
    trace_id: str,
    manager: ObservabilityManager = Depends(get_observability_manager),
) -> ExecutionTrace:
    trace = await manager.get_trace(trace_id)
    if trace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trace not found")
    return trace


@router.get("/metrics", response_model=MetricsSnapshot)
async def get_metrics(
    manager: ObservabilityManager = Depends(get_observability_manager),
) -> MetricsSnapshot:
    return manager.get_metrics()
