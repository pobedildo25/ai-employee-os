from typing import Any

from app.adapters.telegram.models import (
    InboundMedia,
    TelegramCallbackRequest,
    TelegramExecutionRequest,
    TelegramMessage,
    TelegramUpdate,
)


class TelegramMapper:
    """Maps Telegram Update → transport requests. No business logic."""

    def map_update(self, update: TelegramUpdate | dict[str, Any]) -> TelegramExecutionRequest | None:
        parsed = update if isinstance(update, TelegramUpdate) else TelegramUpdate.model_validate(update)
        message = parsed.message
        if message is None:
            return None

        media = _extract_media(message)
        user_input = _resolve_user_input(message, media)
        if not user_input and not media:
            return None

        user = message.from_user
        telegram_user_id = user.id if user is not None else message.chat.id
        username = user.username if user is not None else None

        media_meta = [item.model_dump() for item in media]
        return TelegramExecutionRequest(
            user_input=user_input,
            telegram_user_id=telegram_user_id,
            telegram_chat_id=message.chat.id,
            telegram_message_id=message.message_id,
            telegram_username=username,
            media=media,
            metadata={
                "source": "telegram",
                "telegram_user_id": telegram_user_id,
                "telegram_chat_id": message.chat.id,
                "telegram_message_id": message.message_id,
                "telegram_username": username,
                "telegram_update_id": parsed.update_id,
                "telegram_media": media_meta,
            },
            context={
                "channel": "telegram",
                "telegram_user_id": telegram_user_id,
                "telegram_chat_id": message.chat.id,
                "has_media": bool(media),
            },
        )

    def map_callback(self, update: TelegramUpdate | dict[str, Any]) -> TelegramCallbackRequest | None:
        parsed = update if isinstance(update, TelegramUpdate) else TelegramUpdate.model_validate(update)
        callback = parsed.callback_query
        if callback is None or not callback.data:
            return None

        action = _parse_callback_action(callback.data)
        if action is None:
            return None

        chat_id = callback.message.chat.id if callback.message is not None else callback.from_user.id
        return TelegramCallbackRequest(
            action=action,
            telegram_user_id=callback.from_user.id,
            telegram_chat_id=chat_id,
            callback_query_id=callback.id,
            callback_data=callback.data,
            telegram_message_id=callback.message.message_id if callback.message else None,
            metadata={
                "source": "telegram",
                "telegram_user_id": callback.from_user.id,
                "telegram_chat_id": chat_id,
                "telegram_callback_id": callback.id,
            },
        )

    @staticmethod
    def extract_reply_text(state: dict[str, Any]) -> str:
        """Read reply fields from AgentState — does not generate text."""
        result = state.get("result")
        if isinstance(result, dict):
            for key in ("message", "response_message", "text"):
                value = result.get(key)
                if value:
                    return str(value)

        decision = state.get("decision")
        if isinstance(decision, dict):
            for key in ("response_message", "clarification_question", "message"):
                value = decision.get(key)
                if value:
                    return str(value)

        understanding = state.get("understanding")
        if isinstance(understanding, dict) and understanding.get("summary"):
            return str(understanding["summary"])

        status = state.get("status")
        return str(status) if status else "ok"


def _resolve_user_input(message: TelegramMessage, media: list[InboundMedia]) -> str:
    text = (message.text or message.caption or "").strip()
    if text:
        return text
    # Media-only message: synthesize a default instruction so downstream
    # ingestion has a goal to work with.
    if media:
        kind = media[0].kind
        if kind in {"voice", "audio", "video_note"}:
            return "Расшифруй и проанализируй это аудио."
        if kind == "photo":
            return "Посмотри на это изображение и опиши, что на нём."
        if kind == "document":
            return "Изучи этот документ и сделай краткое резюме."
    return ""


def _extract_media(message: TelegramMessage) -> list[InboundMedia]:
    media: list[InboundMedia] = []
    if message.photo:
        # Telegram sends multiple sizes; the last one is the highest resolution.
        largest = message.photo[-1]
        media.append(
            InboundMedia(
                kind="photo",
                file_id=largest.file_id,
                mime_type="image/jpeg",
                file_size=largest.file_size,
            )
        )
    if message.document is not None:
        media.append(
            InboundMedia(
                kind="document",
                file_id=message.document.file_id,
                filename=message.document.file_name,
                mime_type=message.document.mime_type,
                file_size=message.document.file_size,
            )
        )
    if message.voice is not None:
        media.append(
            InboundMedia(
                kind="voice",
                file_id=message.voice.file_id,
                mime_type=message.voice.mime_type or "audio/ogg",
                file_size=message.voice.file_size,
                duration=message.voice.duration,
            )
        )
    if message.audio is not None:
        media.append(
            InboundMedia(
                kind="audio",
                file_id=message.audio.file_id,
                filename=message.audio.file_name,
                mime_type=message.audio.mime_type or "audio/mpeg",
                file_size=message.audio.file_size,
                duration=message.audio.duration,
            )
        )
    if message.video_note is not None:
        media.append(
            InboundMedia(
                kind="video_note",
                file_id=message.video_note.file_id,
                mime_type="video/mp4",
                file_size=message.video_note.file_size,
                duration=message.video_note.duration,
            )
        )
    return media


def _parse_callback_action(data: str) -> str | None:
    if not data.startswith("tg:"):
        return None
    action = data.split(":", 1)[1]
    if action in {"approve", "cancel", "revise", "retry"}:
        return action
    return None
