import re
import time
from typing import Any

from app.adapters.telegram.presenter import format_progress_header, format_telegram_progress
from app.adapters.telegram.sender import TelegramSender


class TelegramProgressMessenger:
    """Edits a single Telegram message for execution progress with throttling."""

    def __init__(
        self,
        sender: TelegramSender,
        *,
        min_interval_seconds: float = 2.0,
    ) -> None:
        self._sender = sender
        self._min_interval = min_interval_seconds
        self._last_sent_at: dict[int, float] = {}

    async def start(self, chat_id: int, *, reply_to_message_id: int | None = None) -> int | None:
        result = await self._sender.send_message(
            chat_id,
            format_progress_header(),
            reply_to_message_id=reply_to_message_id,
        )
        message_id = _extract_message_id(result)
        if message_id is not None:
            self._last_sent_at[message_id] = 0.0
        return message_id

    async def maybe_update(
        self,
        chat_id: int,
        message_id: int | None,
        progress: dict[str, Any] | None,
        *,
        final: bool = False,
    ) -> int | None:
        if message_id is None:
            message_id = await self.start(chat_id)
            if message_id is None:
                return None

        now = time.monotonic()
        last = self._last_sent_at.get(message_id, 0.0)
        if not final and now - last < self._min_interval:
            return message_id

        text = format_telegram_progress(progress)
        result = await self._sender.edit_message_text(chat_id, message_id, text)
        self._last_sent_at[message_id] = now
        return _extract_message_id(result) or message_id

    async def finalize(
        self,
        chat_id: int,
        message_id: int | None,
        progress: dict[str, Any] | None,
    ) -> None:
        if message_id is None:
            return
        await self.maybe_update(chat_id, message_id, progress, final=True)

    async def dismiss(
        self,
        chat_id: int,
        message_id: int | None,
        *,
        text: str = "⚠️ Задача прервана",
    ) -> None:
        if message_id is None:
            return
        try:
            await self._sender.edit_message_text(chat_id, message_id, text)
        except Exception:
            return


def _extract_message_id(result: dict[str, Any]) -> int | None:
    payload = result.get("result")
    if isinstance(payload, dict) and payload.get("message_id") is not None:
        return int(payload["message_id"])
    if result.get("message_id") is not None:
        return int(result["message_id"])
    return None
