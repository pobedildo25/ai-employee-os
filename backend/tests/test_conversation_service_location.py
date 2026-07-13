"""P0-C extraction location checks — ConversationService owns dialog FSM."""

from app.adapters.telegram.conversation_store import (
    TelegramConversationStore,
    get_conversation_store_singleton as telegram_get_store,
)
from app.adapters.telegram.flow import TelegramProductFlow
from app.conversation.service import ConversationService
from app.conversation.store import (
    ConversationStore,
    get_conversation_store_singleton as conversation_get_store,
)


def test_conversation_service_importable_from_application_layer() -> None:
    assert ConversationService is not None
    assert ConversationService.__module__ == "app.conversation.service"


def test_telegram_product_flow_is_conversation_service_subclass() -> None:
    assert issubclass(TelegramProductFlow, ConversationService)


def test_conversation_store_singleton_reexport_same_type() -> None:
    assert conversation_get_store is telegram_get_store
    store = conversation_get_store()
    assert isinstance(store, ConversationStore)
    assert isinstance(store, TelegramConversationStore)
    assert type(store) is ConversationStore
