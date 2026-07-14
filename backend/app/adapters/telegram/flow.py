from typing import Any

from app.adapters.telegram.channel import (
    TelegramArtifactCollector,
    TelegramChannelNotifier,
    TelegramSessionPort,
)
from app.adapters.telegram.continuation import TelegramArtifactDelivery, TelegramGraphContinuation
from app.adapters.telegram.models import TelegramCallbackRequest, TelegramExecutionRequest
from app.adapters.telegram.progress import TelegramProgressMessenger
from app.adapters.telegram.sender import TelegramSender
from app.adapters.telegram.session import TelegramSessionManager
from app.agent_runtime.runtime import AgentRuntime
from app.agents.executive.agent import ExecutiveAgent
from app.conversation.requests import CallbackRequest, UserMessageRequest
from app.conversation.service import ConversationService
from app.orchestration.orchestrator import Orchestrator


def to_user_message_request(request: TelegramExecutionRequest) -> UserMessageRequest:
    return UserMessageRequest(
        user_id=request.telegram_user_id,
        chat_id=request.telegram_chat_id,
        text=request.user_input,
        message_id=request.telegram_message_id,
        username=request.telegram_username,
        metadata=dict(request.metadata),
        context=dict(request.context),
    )


def to_callback_request(request: TelegramCallbackRequest) -> CallbackRequest:
    return CallbackRequest(
        action=request.action,
        user_id=request.telegram_user_id,
        chat_id=request.telegram_chat_id,
        callback_id=request.callback_query_id,
        callback_data=request.callback_data,
        message_id=request.telegram_message_id,
        metadata=dict(request.metadata),
    )


def build_telegram_conversation_service(
    *,
    runtime: AgentRuntime,
    session_manager: TelegramSessionManager,
    sender: TelegramSender,
    conversation_store,
    progress_messenger: TelegramProgressMessenger | None = None,
    continuation: TelegramGraphContinuation | None = None,
    artifact_delivery: TelegramArtifactDelivery | None = None,
    orchestrator: Orchestrator | None = None,
    executive_agent: ExecutiveAgent | None = None,
    allowed_user_ids: set[int] | None = None,
    business_client_resolver=None,
    memory_capture=None,
    client_work_summary=None,
) -> ConversationService:
    delivery = artifact_delivery or TelegramArtifactDelivery(None, None)
    progress = progress_messenger or TelegramProgressMessenger(sender)
    return ConversationService(
        runtime=runtime,
        store=conversation_store,
        sessions=TelegramSessionPort(session_manager),
        notifier=TelegramChannelNotifier(
            sender,
            progress=progress,
            artifact_delivery=delivery,
        ),
        artifacts=TelegramArtifactCollector(delivery),
        continuation=continuation,
        orchestrator=orchestrator,
        executive_agent=executive_agent,
        allowed_user_ids=allowed_user_ids,
        business_client_resolver=business_client_resolver,
        memory_capture=memory_capture,
        client_work_summary=client_work_summary,
    )


class TelegramProductFlow:
    """Thin Telegram adapter: map DTOs → ConversationService. No dialog FSM here."""

    def __init__(
        self,
        service: ConversationService | None = None,
        /,
        **telegram_kwargs: Any,
    ) -> None:
        if service is not None and telegram_kwargs:
            raise TypeError("pass ConversationService or telegram wiring kwargs, not both")
        if service is not None:
            self._service = service
        else:
            self._service = build_telegram_conversation_service(**telegram_kwargs)

    @property
    def service(self) -> ConversationService:
        return self._service

    async def handle_message(self, request: TelegramExecutionRequest) -> dict[str, Any]:
        return await self._service.handle_message(to_user_message_request(request))

    async def handle_callback(self, request: TelegramCallbackRequest) -> dict[str, Any]:
        return await self._service.handle_callback(to_callback_request(request))

    # Test / legacy attribute shims — poke through to ConversationService.
    @property
    def _executive_agent(self):
        return self._service._executive_agent

    @_executive_agent.setter
    def _executive_agent(self, value) -> None:
        self._service._executive_agent = value

    @property
    def _runtime(self):
        return self._service._runtime

    @_runtime.setter
    def _runtime(self, value) -> None:
        self._service._runtime = value
