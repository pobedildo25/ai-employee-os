from typing import Any

from app.adapters.telegram.models import (
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

        user_input = _resolve_user_input(message)
        if not user_input:
            return None

        user = message.from_user
        telegram_user_id = user.id if user is not None else message.chat.id
        username = user.username if user is not None else None

        media_meta = _media_metadata(message)

        return TelegramExecutionRequest(
            user_input=user_input,
            telegram_user_id=telegram_user_id,
            telegram_chat_id=message.chat.id,
            telegram_message_id=message.message_id,
            telegram_username=username,
            metadata={
                "source": "telegram",
                "telegram_user_id": telegram_user_id,
                "telegram_chat_id": message.chat.id,
                "telegram_message_id": message.message_id,
                "telegram_username": username,
                "telegram_update_id": parsed.update_id,
                **media_meta,
            },
            context={
                "channel": "telegram",
                "telegram_user_id": telegram_user_id,
                "telegram_chat_id": message.chat.id,
                **media_meta,
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
        from app.conversation.messages import extract_reply_text

        return extract_reply_text(state)


def _resolve_user_input(message: TelegramMessage) -> str | None:
    """Accept text, caption, or media-only messages (photo/document)."""
    text = (message.text or message.caption or "").strip()
    has_photo = bool(message.photo)
    has_document = message.document is not None

    if not text and not has_photo and not has_document:
        return None

    parts: list[str] = []
    if text:
        parts.append(text)

    if has_photo:
        parts.append(
            "[К сообщению прикреплено фото. Используй его как визуальный референс/"
            "образец структуры и стиля документа, если пользователь просит сделать "
            "по аналогии.]"
        )
    if has_document and message.document is not None:
        name = message.document.file_name or "файл"
        mime = message.document.mime_type or "unknown"
        parts.append(f"[К сообщению прикреплён файл: {name} ({mime}).]")

    return "\n\n".join(parts).strip() or None


def _media_metadata(message: TelegramMessage) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    if message.photo:
        largest = message.photo[-1]
        meta["telegram_photo_file_id"] = largest.file_id
        meta["has_photo"] = True
    if message.document is not None:
        meta["telegram_document_file_id"] = message.document.file_id
        meta["telegram_document_file_name"] = message.document.file_name
        meta["telegram_document_mime_type"] = message.document.mime_type
        meta["has_document"] = True
    return meta


def _parse_callback_action(data: str) -> str | None:
    if not data.startswith("tg:"):
        return None
    action = data.split(":", 1)[1]
    if action in {"approve", "cancel", "revise", "retry"}:
        return action
    return None
