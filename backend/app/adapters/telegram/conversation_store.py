from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TelegramFlowMode(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    REVISION_PROMPTED = "revision_prompted"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TelegramConversationState(BaseModel):
    telegram_user_id: int
    telegram_chat_id: int
    workspace_id: str | None = None
    session_id: str | None = None
    flow_mode: TelegramFlowMode = TelegramFlowMode.IDLE
    last_user_input: str | None = None
    last_execution_id: str | None = None
    last_agent_state: dict[str, Any] | None = None
    progress_message_id: int | None = None
    artifact_ids: list[str] = Field(default_factory=list)
    revision_prompted_at: datetime | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now())


class TelegramConversationStore:
    """Transport-only state for multi-turn Telegram UX. No business rules."""

    def __init__(self) -> None:
        self._states: dict[int, TelegramConversationState] = {}

    def get(self, telegram_user_id: int) -> TelegramConversationState | None:
        return self._states.get(telegram_user_id)

    def get_or_create(self, telegram_user_id: int, telegram_chat_id: int) -> TelegramConversationState:
        existing = self._states.get(telegram_user_id)
        if existing is not None:
            return existing
        state = TelegramConversationState(
            telegram_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
        )
        self._states[telegram_user_id] = state
        return state

    def save(self, state: TelegramConversationState) -> None:
        state.updated_at = datetime.now()
        self._states[state.telegram_user_id] = state

    def clear_flow(self, telegram_user_id: int) -> None:
        state = self._states.get(telegram_user_id)
        if state is None:
            return
        state.flow_mode = TelegramFlowMode.IDLE
        state.progress_message_id = None
        state.revision_prompted_at = None
        self.save(state)
