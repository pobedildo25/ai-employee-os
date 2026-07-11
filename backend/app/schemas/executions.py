from typing import Any

from pydantic import BaseModel, Field

from app.orchestration.models import ExecutionState, TelegramProgressMessage


class ExecutionDetailResponse(BaseModel):
    execution_id: str
    trace_id: str = ""
    status: str
    progress: float = 0.0
    execution_graph: dict[str, Any] | None = None
    execution_state: dict[str, Any] | None = None
    task_plan: dict[str, Any] | None = None
    task_execution: dict[str, Any] | None = None
    active_nodes: list[str] = Field(default_factory=list)
    completed_nodes: list[str] = Field(default_factory=list)
    failed_nodes: list[str] = Field(default_factory=list)


class ExecutionProgressResponse(BaseModel):
    execution_id: str
    progress: float
    progress_percent: int
    telegram_progress: TelegramProgressMessage | None = None
    execution_state: ExecutionState | None = None


class ExecutionControlResponse(BaseModel):
    execution_id: str
    status: str
    execution_state: ExecutionState
