from typing import Any

from app.orchestration.models import ExecutionGraph, ExecutionState
from app.planning.models import TaskExecution


def parse_execution_graph(raw: dict[str, Any]) -> ExecutionGraph:
    return ExecutionGraph.model_validate(raw)


def parse_execution_state(raw: dict[str, Any]) -> ExecutionState:
    return ExecutionState.model_validate(raw)


def parse_task_execution(raw: dict[str, Any] | None) -> TaskExecution | None:
    if raw is None:
        return None
    return TaskExecution.model_validate(raw)
