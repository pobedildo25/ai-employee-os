from app.conversation.service import ConversationService


class TelegramProductFlow(ConversationService):
    """Telegram adapter facade over ConversationService. Prefer ConversationService for new code."""
