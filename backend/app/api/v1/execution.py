from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.agent_runtime.exceptions import GraphExecutionError
from app.agent_runtime.runtime import AgentRuntime
from app.api.v1.dependencies import get_agent_runtime
from app.schemas.execution import ExecutionRunRequest, ExecutionRunResponse

router = APIRouter(prefix="/execution", tags=["execution"])


@router.post("/run", response_model=ExecutionRunResponse)
async def run_execution(
    data: ExecutionRunRequest,
    request: Request,
    runtime: AgentRuntime = Depends(get_agent_runtime),
) -> ExecutionRunResponse:
    context = dict(data.context)
    if data.client_id is not None:
        context.setdefault("client_id", str(data.client_id))
    if data.project_id is not None:
        context.setdefault("project_id", str(data.project_id))

    metadata = dict(data.metadata)
    if data.client_id is not None:
        metadata.setdefault("client_id", str(data.client_id))
    if data.project_id is not None:
        metadata.setdefault("project_id", str(data.project_id))

    trace_id = getattr(request.state, "trace_id", None)

    try:
        state = await runtime.execute(
            data.user_input,
            trace_id=trace_id,
            context=context,
            metadata=metadata,
        )
    except GraphExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return ExecutionRunResponse(
        execution_id=str(state.get("execution_id", "")),
        trace_id=str(state.get("trace_id", trace_id or "")),
        status=str(state.get("status", "unknown")),
        result=state.get("result"),
        current_step=state.get("current_step"),
        decision=state.get("decision"),
        understanding=state.get("understanding"),
    )
