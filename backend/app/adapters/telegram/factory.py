from app.adapters.telegram.bot import TelegramAdapter, TelegramBot
from app.adapters.telegram.mapper import TelegramMapper
from app.adapters.telegram.sender import HttpTelegramSender, InMemoryTelegramSender, TelegramSender
from app.adapters.telegram.session import TelegramSessionManager
from app.agent_runtime.runtime import AgentRuntime
from app.core.config import Settings
from app.workspace.service import WorkspaceService


def create_telegram_adapter(
    *,
    runtime: AgentRuntime,
    workspace_service: WorkspaceService,
    settings: Settings,
    sender: TelegramSender | None = None,
) -> TelegramAdapter:
    """Wire Telegram transport to existing runtime/workspace. No new singletons."""
    if sender is None:
        if settings.telegram_bot_token:
            sender = HttpTelegramSender(settings.telegram_bot_token)
        else:
            sender = InMemoryTelegramSender()

    session_manager = TelegramSessionManager(workspace_service=workspace_service)
    return TelegramAdapter(
        runtime=runtime,
        session_manager=session_manager,
        sender=sender,
        mapper=TelegramMapper(),
        enabled=settings.telegram_enabled,
    )


def create_telegram_bot(
    *,
    runtime: AgentRuntime,
    workspace_service: WorkspaceService,
    settings: Settings,
    sender: TelegramSender | None = None,
) -> TelegramBot:
    adapter = create_telegram_adapter(
        runtime=runtime,
        workspace_service=workspace_service,
        settings=settings,
        sender=sender,
    )
    return TelegramBot(adapter, token=settings.telegram_bot_token or None)
