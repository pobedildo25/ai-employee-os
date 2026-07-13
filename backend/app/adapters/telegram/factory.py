from collections.abc import Awaitable, Callable
import logging

from app.adapters.telegram.bot import TelegramAdapter, TelegramBot
from app.adapters.telegram.conversation_store import TelegramConversationStore
from app.adapters.telegram.mapper import TelegramMapper
from app.adapters.telegram.sender import HttpTelegramSender, InMemoryTelegramSender, TelegramSender
from app.adapters.telegram.session import TelegramSessionManager
from app.agent_runtime.runtime import AgentRuntime
from app.agents.executive.agent import ExecutiveAgent
from app.core.config import Settings
from app.orchestration.orchestrator import Orchestrator
from app.repositories.client_repository import ClientRepository
from app.services.artifact_service import ArtifactService
from app.skills.registry import CapabilityRegistry
from app.storage.storage_interface import StorageInterface
from app.workspace.service import WorkspaceService

logger = logging.getLogger(__name__)

DbRelease = Callable[[], Awaitable[None]]


def create_telegram_adapter(
    *,
    runtime: AgentRuntime,
    workspace_service: WorkspaceService,
    settings: Settings,
    sender: TelegramSender | None = None,
    artifact_service: ArtifactService | None = None,
    storage: StorageInterface | None = None,
    orchestrator: Orchestrator | None = None,
    conversation_store: TelegramConversationStore | None = None,
    capability_registry: CapabilityRegistry | None = None,
    client_repository: ClientRepository | None = None,
    executive_agent: ExecutiveAgent | None = None,
    db_release: DbRelease | None = None,
    redis_client=None,
) -> TelegramAdapter:
    """Wire Telegram transport to existing runtime/workspace. No new singletons."""
    if sender is None:
        if settings.telegram_bot_token:
            sender = HttpTelegramSender(settings.telegram_bot_token)
        else:
            sender = InMemoryTelegramSender()

    allowed_user_ids = settings.parsed_telegram_allowed_user_ids()
    if settings.is_production and not allowed_user_ids:
        logger.warning(
            "telegram allowlist empty in production — all users accepted until configured"
        )

    if redis_client is None:
        try:
            from app.database.redis import get_redis_client

            redis_client = get_redis_client(settings)
        except Exception as exc:
            logger.warning("telegram session bindings: Redis unavailable | error=%s", exc)
            redis_client = None

    session_manager = TelegramSessionManager(
        workspace_service=workspace_service,
        client_repository=client_repository,
        redis_client=redis_client,
        db_release=db_release,
    )
    return TelegramAdapter(
        runtime=runtime,
        session_manager=session_manager,
        sender=sender,
        mapper=TelegramMapper(),
        enabled=settings.telegram_enabled,
        artifact_service=artifact_service,
        storage=storage,
        orchestrator=orchestrator,
        conversation_store=conversation_store,
        capability_registry=capability_registry,
        executive_agent=executive_agent,
        allowed_user_ids=allowed_user_ids,
    )


def create_telegram_bot(
    *,
    runtime: AgentRuntime,
    workspace_service: WorkspaceService,
    settings: Settings,
    sender: TelegramSender | None = None,
    artifact_service: ArtifactService | None = None,
    storage: StorageInterface | None = None,
    orchestrator: Orchestrator | None = None,
    client_repository: ClientRepository | None = None,
    executive_agent: ExecutiveAgent | None = None,
    capability_registry: CapabilityRegistry | None = None,
    conversation_store: TelegramConversationStore | None = None,
    db_release: DbRelease | None = None,
    redis_client=None,
) -> TelegramBot:
    adapter = create_telegram_adapter(
        runtime=runtime,
        workspace_service=workspace_service,
        settings=settings,
        sender=sender,
        artifact_service=artifact_service,
        storage=storage,
        orchestrator=orchestrator,
        conversation_store=conversation_store,
        client_repository=client_repository,
        executive_agent=executive_agent,
        capability_registry=capability_registry,
        db_release=db_release,
        redis_client=redis_client,
    )
    return TelegramBot(adapter, token=settings.telegram_bot_token or None)
