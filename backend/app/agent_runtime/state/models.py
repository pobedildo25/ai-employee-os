from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """Base state schema for LangGraph workflow execution."""

    execution_id: str
    trace_id: str
    user_input: str
    messages: list[dict[str, Any]]
    context: dict[str, Any]
    execution_context: dict[str, Any]
    metadata: dict[str, Any]
    current_step: str | None
    understanding: dict[str, Any]
    decision: dict[str, Any]
    required_capabilities: dict[str, Any]
    task_plan: dict[str, Any] | None
    task_execution: dict[str, Any] | None
    document_creation_result: dict[str, Any] | None
    document_ast: dict[str, Any] | None
    review_result: dict[str, Any] | None
    revision_request: dict[str, Any] | None
    quality_check: dict[str, Any] | None
    render_result: dict[str, Any] | None
    result: dict[str, Any] | None
    status: str


def create_initial_state(
    *,
    execution_id: str,
    trace_id: str,
    user_input: str,
    context: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> AgentState:
    return AgentState(
        execution_id=execution_id,
        trace_id=trace_id,
        user_input=user_input,
        messages=[],
        context=context or {},
        metadata=metadata or {},
        current_step=None,
        result=None,
        status="pending",
    )
