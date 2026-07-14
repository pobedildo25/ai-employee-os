from typing import Any

from pydantic import BaseModel, Field


class TelegramUser(BaseModel):
    id: int
    is_bot: bool = False
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None


class TelegramChat(BaseModel):
    id: int
    type: str = "private"
    title: str | None = None
    username: str | None = None


class TelegramMessage(BaseModel):
    message_id: int
    date: int | None = None
    text: str | None = None
    caption: str | None = None
    photo: list[dict[str, Any]] | None = None
    document: dict[str, Any] | None = None
    voice: dict[str, Any] | None = None
    audio: dict[str, Any] | None = None
    video: dict[str, Any] | None = None
    chat: TelegramChat
    from_user: TelegramUser | None = Field(default=None, alias="from")

    model_config = {"populate_by_name": True}

    def unsupported_media_kind(self) -> str | None:
        if self.photo:
            return "photo"
        if self.voice or self.audio:
            return "voice"
        if self.document or self.video:
            return "media"
        return None


class TelegramCallbackQuery(BaseModel):
    id: str
    from_user: TelegramUser = Field(alias="from")
    message: TelegramMessage | None = None
    chat_instance: str | None = None
    data: str | None = None

    model_config = {"populate_by_name": True}


class TelegramUpdate(BaseModel):
    update_id: int
    message: TelegramMessage | None = None
    callback_query: TelegramCallbackQuery | None = None


class TelegramExecutionRequest(BaseModel):
    """Internal request produced by TelegramMapper — no business logic."""

    user_input: str
    telegram_user_id: int
    telegram_chat_id: int
    telegram_message_id: int | None = None
    telegram_username: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)


class TelegramCallbackRequest(BaseModel):
    action: str
    telegram_user_id: int
    telegram_chat_id: int
    callback_query_id: str
    callback_data: str
    telegram_message_id: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
