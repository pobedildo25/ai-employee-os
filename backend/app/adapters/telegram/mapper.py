from typing import Any

from app.adapters.telegram.models import TelegramExecutionRequest, TelegramUpdate


class TelegramMapper:
    """Maps Telegram Update → TelegramExecutionRequest. No business logic."""

    def map_update(self, update: TelegramUpdate | dict[str, Any]) -> TelegramExecutionRequest | None:
        parsed = update if isinstance(update, TelegramUpdate) else TelegramUpdate.model_validate(update)
        message = parsed.message
        if message is None or not message.text:
            return None

        user = message.from_user
        telegram_user_id = user.id if user is not None else message.chat.id
        username = user.username if user is not None else None

        return TelegramExecutionRequest(
            user_input=message.text,
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
            },
            context={
                "channel": "telegram",
                "telegram_user_id": telegram_user_id,
                "telegram_chat_id": message.chat.id,
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
