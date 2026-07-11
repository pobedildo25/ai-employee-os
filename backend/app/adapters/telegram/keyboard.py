from typing import Any


def approval_keyboard() -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Начать", "callback_data": "tg:approve"},
                {"text": "❌ Отмена", "callback_data": "tg:cancel"},
            ]
        ]
    }


def revision_keyboard() -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [{"text": "🔄 Переделать", "callback_data": "tg:revise"}],
        ]
    }


def retry_keyboard() -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [{"text": "🔁 Попробовать снова", "callback_data": "tg:retry"}],
        ]
    }
