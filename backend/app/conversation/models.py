from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class FlowMode(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    REVISION_PROMPTED = "revision_prompted"
    PENDING_CLARIFICATION = "pending_clarification"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PendingClarification(BaseModel):
    pending_task: bool = True
    original_goal: str
    original_user_input: str
    intent: str = "ASK_CLARIFICATION"
    missing_information: list[str] = Field(default_factory=list)
    understanding: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now())


class ConversationState(BaseModel):
    # telegram_* field names kept for this PR to minimize churn; channel-neutral rename later.
    telegram_user_id: int
    telegram_chat_id: int
    workspace_id: str | None = None
    session_id: str | None = None
    flow_mode: FlowMode = FlowMode.IDLE
    last_user_input: str | None = None
    last_execution_id: str | None = None
    last_agent_state: dict[str, Any] | None = None
    progress_message_id: int | None = None
    artifact_ids: list[str] = Field(default_factory=list)
    revision_prompted_at: datetime | None = None
    pending_clarification: PendingClarification | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now())
