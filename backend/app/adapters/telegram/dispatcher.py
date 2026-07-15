from typing import Any

from app.adapters.telegram.flow import TelegramProductFlow
from app.adapters.telegram.handlers import TelegramMessageHandler
from app.adapters.telegram.mapper import TelegramMapper
from app.adapters.telegram.models import TelegramUpdate
from app.adapters.telegram.sender import TelegramSender
from app.ux.status_copy import UNSUPPORTED_MEDIA, UNSUPPORTED_PHOTO, UNSUPPORTED_VOICE


class TelegramDispatcher:
    """Dispatches Telegram updates to product flow handlers."""

    def __init__(
        self,
        handler: TelegramMessageHandler,
        mapper: TelegramMapper | None = None,
        product_flow: TelegramProductFlow | None = None,
        sender: TelegramSender | None = None,
    ) -> None:
        self._handler = handler
        self._mapper = mapper or TelegramMapper()
        self._flow = product_flow
        self._sender = sender

    async def dispatch(self, update: TelegramUpdate | dict[str, Any]) -> dict[str, Any] | None:
        if self._flow is not None:
            parsed = update if isinstance(update, TelegramUpdate) else TelegramUpdate.model_validate(update)
            callback = self._mapper.map_callback(parsed)
            if callback is not None:
                return await self._flow.handle_callback(callback)
            request = self._mapper.map_update(parsed)
            if request is not None:
                return await self._flow.handle_message(request)
            return await self._decline_unsupported_media(parsed)

        request = self._mapper.map_update(update)
        if request is None:
            return None
        return await self._handler.handle(request)

    async def _decline_unsupported_media(self, update: TelegramUpdate) -> dict[str, Any] | None:
        message = update.message
        if message is None or self._sender is None:
            return None
        kind = message.unsupported_media_kind()
        if kind is None:
            return None
        text = {
            "photo": UNSUPPORTED_PHOTO,
            "voice": UNSUPPORTED_VOICE,
        }.get(kind, UNSUPPORTED_MEDIA)
        send_result = await self._sender.send_message(
            message.chat.id,
            text,
            reply_to_message_id=message.message_id,
        )
        return {
            "status": "unsupported_media",
            "media_kind": kind,
            "send_result": send_result,
        }
