from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ExecutionRunRequest(BaseModel):
    user_input: str = Field(min_length=1)
    client_id: UUID | None = None
    project_id: UUID | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionRunResponse(BaseModel):
    execution_id: str
    trace_id: str
    status: str
    result: dict[str, Any] | None = None
    current_step: str | None = None
    decision: dict[str, Any] | None = None
    understanding: dict[str, Any] | None = None
