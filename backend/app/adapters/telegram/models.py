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


class TelegramPhotoSize(BaseModel):
    file_id: str
    file_unique_id: str | None = None
    width: int | None = None
    height: int | None = None
    file_size: int | None = None


class TelegramDocument(BaseModel):
    file_id: str
    file_unique_id: str | None = None
    file_name: str | None = None
    mime_type: str | None = None
    file_size: int | None = None


class TelegramVoice(BaseModel):
    file_id: str
    file_unique_id: str | None = None
    duration: int | None = None
    mime_type: str | None = None
    file_size: int | None = None


class TelegramAudio(BaseModel):
    file_id: str
    file_unique_id: str | None = None
    duration: int | None = None
    performer: str | None = None
    title: str | None = None
    file_name: str | None = None
    mime_type: str | None = None
    file_size: int | None = None


class TelegramVideoNote(BaseModel):
    file_id: str
    file_unique_id: str | None = None
    duration: int | None = None
    file_size: int | None = None


class TelegramMessage(BaseModel):
    message_id: int
    date: int | None = None
    text: str | None = None
    caption: str | None = None
    chat: TelegramChat
    from_user: TelegramUser | None = Field(default=None, alias="from")
    photo: list[TelegramPhotoSize] | None = None
    document: TelegramDocument | None = None
    voice: TelegramVoice | None = None
    audio: TelegramAudio | None = None
    video_note: TelegramVideoNote | None = None

    model_config = {"populate_by_name": True}


class TelegramFile(BaseModel):
    """Result of the getFile Bot API method."""

    file_id: str
    file_unique_id: str | None = None
    file_size: int | None = None
    file_path: str | None = None


class InboundMedia(BaseModel):
    """Normalized inbound attachment produced by the mapper."""

    kind: str  # photo | document | voice | audio | video_note
    file_id: str
    filename: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    duration: int | None = None


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
    media: list[InboundMedia] = Field(default_factory=list)
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
