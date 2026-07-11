from typing import Any

from app.adapters.telegram.handlers import TelegramMessageHandler
from app.adapters.telegram.mapper import TelegramMapper
from app.adapters.telegram.models import TelegramUpdate


class TelegramDispatcher:
    """Dispatches Telegram updates to the message handler. No keyword routing."""

    def __init__(
        self,
        handler: TelegramMessageHandler,
        mapper: TelegramMapper | None = None,
    ) -> None:
        self._handler = handler
        self._mapper = mapper or TelegramMapper()

    async def dispatch(self, update: TelegramUpdate | dict[str, Any]) -> dict[str, Any] | None:
        request = self._mapper.map_update(update)
        if request is None:
            return None
        return await self._handler.handle(request)
