from abc import ABC, abstractmethod
from typing import Any


class TelegramAdapterInterface(ABC):
    """Transport adapter: Telegram Update → AgentRuntime → reply."""

    @abstractmethod
    async def handle_update(self, update: dict[str, Any] | Any) -> dict[str, Any] | None:
        raise NotImplementedError
