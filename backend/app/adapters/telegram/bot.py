from typing import Any

from app.adapters.telegram.dispatcher import TelegramDispatcher
from app.adapters.telegram.handlers import TelegramMessageHandler
from app.adapters.telegram.interfaces.telegram_adapter import TelegramAdapterInterface
from app.adapters.telegram.mapper import TelegramMapper
from app.adapters.telegram.sender import TelegramSender
from app.adapters.telegram.session import TelegramSessionManager
from app.agent_runtime.runtime import AgentRuntime


class TelegramAdapter(TelegramAdapterInterface):
    """Telegram transport adapter over existing AgentRuntime + Workspace."""

    def __init__(
        self,
        *,
        runtime: AgentRuntime,
        session_manager: TelegramSessionManager,
        sender: TelegramSender,
        mapper: TelegramMapper | None = None,
        enabled: bool = True,
    ) -> None:
        self.enabled = enabled
        self._mapper = mapper or TelegramMapper()
        self._handler = TelegramMessageHandler(
            runtime=runtime,
            session_manager=session_manager,
            sender=sender,
            mapper=self._mapper,
        )
        self._dispatcher = TelegramDispatcher(self._handler, mapper=self._mapper)

    @property
    def handler(self) -> TelegramMessageHandler:
        return self._handler

    @property
    def dispatcher(self) -> TelegramDispatcher:
        return self._dispatcher

    async def handle_update(self, update: dict[str, Any] | Any) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        return await self._dispatcher.dispatch(update)


class TelegramBot:
    """Thin bot facade — holds adapter; no business decisions."""

    def __init__(self, adapter: TelegramAdapter, *, token: str | None = None) -> None:
        self._adapter = adapter
        self.token = token

    async def process_update(self, update: dict[str, Any]) -> dict[str, Any] | None:
        return await self._adapter.handle_update(update)
