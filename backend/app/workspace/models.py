from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class WorkspaceSessionStatus(str, Enum):
    ACTIVE = "active"
    FINISHED = "finished"


class Workspace(BaseModel):
    """Working space for an AI Employee — agent work state, not a user UI."""

    id: UUID = Field(default_factory=uuid4)
    client_id: UUID
    active_project_id: UUID | None = None
    active_session_id: UUID | None = None
    active_task_id: UUID | None = None
    active_artifact_id: UUID | None = None
    active_background_tasks: list[UUID] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: datetime = Field(default_factory=lambda: datetime.now())


class WorkspaceSession(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workspace_id: UUID
    status: WorkspaceSessionStatus = WorkspaceSessionStatus.ACTIVE
    started_at: datetime = Field(default_factory=lambda: datetime.now())
    finished_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Conversation(BaseModel):
    """Session dialogue buffer. Does not replace Memory."""

    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    messages: list[dict[str, Any]] = Field(default_factory=list)
    summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: datetime = Field(default_factory=lambda: datetime.now())
