from typing import Any

from pydantic import BaseModel, Field


class UserMessageRequest(BaseModel):
    user_id: int
    chat_id: int
    text: str
    message_id: int | None = None
    username: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)


class CallbackRequest(BaseModel):
    action: str
    user_id: int
    chat_id: int
    callback_id: str
    callback_data: str
    message_id: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
