from typing import Any

from app.adapters.telegram.conversation_store import TelegramConversationStore
from app.adapters.telegram.continuation import TelegramArtifactDelivery, TelegramGraphContinuation
from app.adapters.telegram.dispatcher import TelegramDispatcher
from app.adapters.telegram.flow import TelegramProductFlow
from app.adapters.telegram.handlers import TelegramMessageHandler
from app.adapters.telegram.interfaces.telegram_adapter import TelegramAdapterInterface
from app.adapters.telegram.mapper import TelegramMapper
from app.adapters.telegram.progress import TelegramProgressMessenger
from app.adapters.telegram.sender import TelegramSender
from app.adapters.telegram.session import TelegramSessionManager
from app.agent_runtime.runtime import AgentRuntime
from app.agents.executive.agent import ExecutiveAgent
from app.orchestration.orchestrator import Orchestrator
from app.quality.gate import QualityGate
from app.quality.nodes.quality_gate_node import QualityGateNode
from app.quality.reviewer import ReviewerAgent
from app.revision.agent import RevisionAgent
from app.revision.manager import RevisionManager
from app.revision.nodes.revision_node import RevisionNode
from app.services.artifact_service import ArtifactService
from app.skills.registry import CapabilityRegistry
from app.storage.storage_interface import StorageInterface


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
        product_flow: TelegramProductFlow | None = None,
        conversation_store: TelegramConversationStore | None = None,
        artifact_service: ArtifactService | None = None,
        storage: StorageInterface | None = None,
        orchestrator: Orchestrator | None = None,
        capability_registry: CapabilityRegistry | None = None,
        executive_agent: ExecutiveAgent | None = None,
        allowed_user_ids: set[int] | None = None,
    ) -> None:
        self.enabled = enabled
        self._mapper = mapper or TelegramMapper()
        self._conversation_store = conversation_store or TelegramConversationStore()
        self._allowed_user_ids = allowed_user_ids or set()
        self._product_flow = product_flow or self._build_product_flow(
            runtime=runtime,
            session_manager=session_manager,
            sender=sender,
            artifact_service=artifact_service,
            storage=storage,
            orchestrator=orchestrator,
            capability_registry=capability_registry,
            executive_agent=executive_agent,
            allowed_user_ids=self._allowed_user_ids,
        )
        self._handler = TelegramMessageHandler(
            runtime=runtime,
            session_manager=session_manager,
            sender=sender,
            mapper=self._mapper,
            product_flow=self._product_flow,
        )
        self._dispatcher = TelegramDispatcher(
            self._handler,
            mapper=self._mapper,
            product_flow=self._product_flow,
        )

    @property
    def handler(self) -> TelegramMessageHandler:
        return self._handler

    @property
    def dispatcher(self) -> TelegramDispatcher:
        return self._dispatcher

    @property
    def conversation_store(self) -> TelegramConversationStore:
        return self._conversation_store

    async def handle_update(self, update: dict[str, Any] | Any) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        return await self._dispatcher.dispatch(update)

    def _build_product_flow(
        self,
        *,
        runtime: AgentRuntime,
        session_manager: TelegramSessionManager,
        sender: TelegramSender,
        artifact_service: ArtifactService | None,
        storage: StorageInterface | None,
        orchestrator: Orchestrator | None,
        capability_registry: CapabilityRegistry | None,
        executive_agent: ExecutiveAgent | None = None,
        allowed_user_ids: set[int] | None = None,
    ) -> TelegramProductFlow:
        continuation = self._build_continuation(capability_registry)
        return TelegramProductFlow(
            runtime=runtime,
            session_manager=session_manager,
            sender=sender,
            conversation_store=self._conversation_store,
            mapper=self._mapper,
            progress_messenger=TelegramProgressMessenger(sender),
            continuation=continuation,
            artifact_delivery=TelegramArtifactDelivery(artifact_service, storage),
            orchestrator=orchestrator,
            executive_agent=executive_agent,
            allowed_user_ids=allowed_user_ids,
        )

    @staticmethod
    def _build_continuation(
        capability_registry: CapabilityRegistry | None = None,
    ) -> TelegramGraphContinuation | None:
        try:
            from app.llm.gateway import create_llm_gateway

            llm_gateway = create_llm_gateway()
            revision_node = RevisionNode(RevisionManager(RevisionAgent(llm_gateway)))
            quality_gate_node = QualityGateNode(QualityGate(ReviewerAgent(llm_gateway)))
            return TelegramGraphContinuation(
                revision_node=revision_node,
                quality_gate_node=quality_gate_node,
                revision_manager=RevisionManager(RevisionAgent(llm_gateway)),
                capability_registry=capability_registry,
            )
        except Exception:
            return None


class TelegramBot:
    """Thin bot facade — holds adapter; no business decisions."""

    def __init__(self, adapter: TelegramAdapter, *, token: str | None = None) -> None:
        self._adapter = adapter
        self.token = token

    async def process_update(self, update: dict[str, Any]) -> dict[str, Any] | None:
        return await self._adapter.handle_update(update)
