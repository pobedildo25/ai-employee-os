import enum
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class PlanStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    READY = "READY"
    APPROVED = "APPROVED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StepStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class TaskExecutionStatus(str, enum.Enum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ApprovalStatus(str, enum.Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    MODIFIED = "MODIFIED"


class PlanStep(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    description: str
    capability: str
    dependencies: list[UUID] = Field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    result: dict[str, Any] | None = None


class TaskPlan(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    goal: str
    summary: str
    steps: list[PlanStep] = Field(default_factory=list)
    required_capabilities: list[str] = Field(default_factory=list)
    status: PlanStatus = PlanStatus.DRAFT
    created_at: datetime = Field(default_factory=lambda: datetime.now())


class ExecutionLogEntry(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now())
    step_id: UUID | None = None
    level: str = "info"
    message: str


class ApprovalState(BaseModel):
    status: ApprovalStatus = ApprovalStatus.NOT_REQUIRED
    requested_at: datetime | None = None
    resolved_at: datetime | None = None
    comment: str | None = None


class TaskExecution(BaseModel):
    task_id: UUID = Field(default_factory=uuid4)
    plan_id: UUID | None = None
    current_step: UUID | None = None
    status: TaskExecutionStatus = TaskExecutionStatus.CREATED
    approval: ApprovalState = Field(default_factory=ApprovalState)
    logs: list[ExecutionLogEntry] = Field(default_factory=list)
    results: dict[str, Any] = Field(default_factory=dict)


class QualityCheckResult(BaseModel):
    passed: bool = True
    score: float = 1.0
    notes: str = ""
    issues: list[str] = Field(default_factory=list)
