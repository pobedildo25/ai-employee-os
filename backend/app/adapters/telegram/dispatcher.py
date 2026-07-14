import logging
from typing import Any

from app.adapters.telegram.flow import TelegramProductFlow
from app.adapters.telegram.handlers import TelegramMessageHandler
from app.adapters.telegram.mapper import TelegramMapper
from app.adapters.telegram.models import TelegramUpdate

logger = logging.getLogger(__name__)


class TelegramDispatcher:
    """Dispatches Telegram updates to product flow handlers."""

    def __init__(
        self,
        handler: TelegramMessageHandler,
        mapper: TelegramMapper | None = None,
        product_flow: TelegramProductFlow | None = None,
    ) -> None:
        self._handler = handler
        self._mapper = mapper or TelegramMapper()
        self._flow = product_flow

    async def dispatch(self, update: TelegramUpdate | dict[str, Any]) -> dict[str, Any] | None:
        if self._flow is not None:
            parsed = update if isinstance(update, TelegramUpdate) else TelegramUpdate.model_validate(update)
            callback = self._mapper.map_callback(parsed)
            if callback is not None:
                return await self._flow.handle_callback(callback)
            request = self._mapper.map_update(parsed)
            if request is not None:
                return await self._flow.handle_message(request)
            msg = parsed.message
            logger.warning(
                "telegram update skipped (no text/caption/media) | update_id=%s has_message=%s",
                parsed.update_id,
                msg is not None,
            )
            return None

        request = self._mapper.map_update(update)
        if request is None:
            return None
        return await self._handler.handle(request)
