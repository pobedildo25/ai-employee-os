from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class TraceStatus(str, Enum):
    STARTED = "started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TimelineEventStatus(str, Enum):
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TimelineEvent(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    node_name: str
    started_at: datetime = Field(default_factory=lambda: datetime.now())
    finished_at: datetime | None = None
    duration_ms: float | None = None
    status: TimelineEventStatus = TimelineEventStatus.STARTED
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionTimeline(BaseModel):
    trace_id: str
    execution_id: str
    events: list[TimelineEvent] = Field(default_factory=list)


class ExecutionTrace(BaseModel):
    trace_id: str
    execution_id: str
    started_at: datetime = Field(default_factory=lambda: datetime.now())
    finished_at: datetime | None = None
    status: TraceStatus = TraceStatus.STARTED
    duration_ms: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    timeline: ExecutionTimeline | None = None


class MetricsSnapshot(BaseModel):
    execution_count: int = 0
    failed_count: int = 0
    average_duration_ms: float = 0.0
    llm_calls: int = 0
    tokens: int = 0
    queue_size: int = 0
    active_traces: int = 0
    completed_traces: int = 0
