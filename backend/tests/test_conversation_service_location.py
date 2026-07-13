"""P0-C extraction location checks — ConversationService owns dialog FSM."""

from pathlib import Path

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


def test_conversation_service_has_no_telegram_imports() -> None:
    source = Path(ConversationService.__module__.replace(".", "/") + ".py")
    # Resolve relative to backend package root (tests run from backend/).
    candidates = [
        Path("app/conversation/service.py"),
        Path(__file__).resolve().parents[1] / "app" / "conversation" / "service.py",
    ]
    path = next(p for p in candidates if p.exists())
    text = path.read_text(encoding="utf-8")
    assert "app.adapters.telegram" not in text


def test_telegram_product_flow_wraps_conversation_service() -> None:
    assert not issubclass(TelegramProductFlow, ConversationService)
    assert hasattr(TelegramProductFlow, "handle_message")
    assert hasattr(TelegramProductFlow, "handle_callback")


def test_conversation_store_singleton_reexport_same_type() -> None:
    assert conversation_get_store is telegram_get_store
    store = conversation_get_store()
    assert isinstance(store, ConversationStore)
    assert isinstance(store, TelegramConversationStore)
    assert type(store) is ConversationStore
