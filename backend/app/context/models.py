from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ContextRequest(BaseModel):
    """Input shared across context providers."""

    user_input: str
    client_id: UUID | None = None
    project_id: UUID | None = None
    session_id: str | None = None
    current_task: dict[str, Any] | None = None
    preferences: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    trace_id: str = "-"


class ExecutionContext(BaseModel):
    """Unified execution context for the Executive Agent."""

    user_input: str
    current_task: dict[str, Any] | None = None
    client_context: dict[str, Any] | None = None
    project_context: dict[str, Any] | None = None
    artifact_context: list[dict[str, Any]] = Field(default_factory=list)
    conversation_history: list[dict[str, Any]] = Field(default_factory=list)
    preferences: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    extensions: dict[str, Any] = Field(default_factory=dict)

    def to_prioritized_dict(self) -> dict[str, Any]:
        from app.context.priority import build_prioritized_context

        return build_prioritized_context(self)
