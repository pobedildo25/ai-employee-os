from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class BackgroundTaskStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class BackgroundTask(BaseModel):
    """Internal background task — no external broker."""

    id: UUID = Field(default_factory=uuid4)
    task_type: str
    status: BackgroundTaskStatus = BackgroundTaskStatus.QUEUED
    priority: int = Field(default=100, ge=0)
    payload: dict[str, Any] = Field(default_factory=dict)
    retry_count: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    started_at: datetime | None = None
    finished_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    result: dict[str, Any] | None = None
