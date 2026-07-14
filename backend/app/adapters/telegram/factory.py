from app.adapters.telegram.bot import TelegramAdapter, TelegramBot
from app.adapters.telegram.conversation_store import TelegramConversationStore
from app.adapters.telegram.mapper import TelegramMapper
from app.adapters.telegram.sender import HttpTelegramSender, InMemoryTelegramSender, TelegramSender
from app.adapters.telegram.session import TelegramSessionManager
from app.agent_runtime.runtime import AgentRuntime
from app.agency.profile import AgencyProfile
from app.agents.executive.agent import ExecutiveAgent
from app.clients.resolver import BusinessClientResolver
from app.core.config import Settings
from app.memory.capture import DialogueMemoryCapture
from app.orchestration.orchestrator import Orchestrator
from app.repositories.client_repository import ClientRepository
from app.services.artifact_service import ArtifactService
from app.skills.registry import CapabilityRegistry
from app.storage.storage_interface import StorageInterface
from app.workspace.service import WorkspaceService


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
    business_client_resolver: BusinessClientResolver | None = None,
    agency_profile: AgencyProfile | None = None,
    memory_capture: DialogueMemoryCapture | None = None,
) -> TelegramAdapter:
    """Wire Telegram transport to existing runtime/workspace. No new singletons."""
    if sender is None:
        if settings.telegram_bot_token:
            sender = HttpTelegramSender(settings.telegram_bot_token)
        else:
            sender = InMemoryTelegramSender()

    session_manager = TelegramSessionManager(
        workspace_service=workspace_service,
        client_repository=client_repository,
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
        business_client_resolver=business_client_resolver,
        agency_profile=agency_profile,
        memory_capture=memory_capture,
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
    business_client_resolver: BusinessClientResolver | None = None,
    agency_profile: AgencyProfile | None = None,
    memory_capture: DialogueMemoryCapture | None = None,
) -> TelegramBot:
    adapter = create_telegram_adapter(
        runtime=runtime,
        workspace_service=workspace_service,
        settings=settings,
        sender=sender,
        artifact_service=artifact_service,
        storage=storage,
        orchestrator=orchestrator,
        client_repository=client_repository,
        executive_agent=executive_agent,
        capability_registry=capability_registry,
        business_client_resolver=business_client_resolver,
        agency_profile=agency_profile,
        memory_capture=memory_capture,
    )
    return TelegramBot(adapter, token=settings.telegram_bot_token or None)
