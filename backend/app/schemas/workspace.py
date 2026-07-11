from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class WorkspaceOpenRequest(BaseModel):
    client_id: UUID
    project_id: UUID | None = None
    task_id: UUID | None = None
    artifact_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    open_session: bool = True


class WorkspaceSnapshot(BaseModel):
    workspace_id: str
    client_id: str
    active_project_id: str | None = None
    active_session_id: str | None = None
    active_task_id: str | None = None
    active_artifact_id: str | None = None
    active_background_tasks: list[str] = Field(default_factory=list)
    session: dict[str, Any] | None = None
    conversation: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
