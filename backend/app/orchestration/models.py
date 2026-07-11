import enum
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class NodeStatus(str, enum.Enum):
    WAITING = "WAITING"
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PAUSED = "PAUSED"


class ExecutionControlStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ExecutionGraphNode(BaseModel):
    id: UUID
    capability: str
    description: str
    status: NodeStatus = NodeStatus.WAITING
    dependencies: list[UUID] = Field(default_factory=list)
    result: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    retry_count: int = 0


class ExecutionGraph(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    plan_id: UUID
    goal: str = ""
    nodes: dict[str, ExecutionGraphNode] = Field(default_factory=dict)
    edges: list[tuple[str, str]] = Field(default_factory=list)
    execution_order: list[str] = Field(default_factory=list)


class ExecutionState(BaseModel):
    execution_id: str
    graph_id: UUID
    control_status: ExecutionControlStatus = ExecutionControlStatus.RUNNING
    current_nodes: list[str] = Field(default_factory=list)
    completed_nodes: list[str] = Field(default_factory=list)
    failed_nodes: list[str] = Field(default_factory=list)
    waiting_nodes: list[str] = Field(default_factory=list)
    progress: float = 0.0
    started_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: datetime = Field(default_factory=lambda: datetime.now())
    failure_reason: str | None = None


class TelegramProgressLine(BaseModel):
    title: str
    status_icon: str
    status_label: str


class TelegramProgressMessage(BaseModel):
    execution_id: str
    progress_percent: int
    lines: list[TelegramProgressLine] = Field(default_factory=list)


class ExecutionRecord(BaseModel):
    execution_id: str
    trace_id: str = ""
    graph: ExecutionGraph
    state: ExecutionState
    task_plan: dict[str, Any] | None = None
    task_execution: dict[str, Any] | None = None
    telegram_progress: TelegramProgressMessage | None = None
