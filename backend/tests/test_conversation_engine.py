"""Stage B — Conversation Engine regression tests."""

from __future__ import annotations

from typing import Any

import pytest

from app.adapters.telegram.conversation_store import (
    TelegramConversationStore,
    TelegramFlowMode,
    get_conversation_store_singleton,
)
from app.adapters.telegram.factory import create_telegram_adapter
from app.adapters.telegram.flow import TelegramProductFlow
from app.adapters.telegram.models import TelegramCallbackRequest, TelegramExecutionRequest
from app.adapters.telegram.progress import TelegramProgressMessenger
from app.adapters.telegram.sender import InMemoryTelegramSender
from app.adapters.telegram.session import TelegramSessionManager
from app.agents.decision.models import AgentDecision, DecisionType
from app.agents.executive.models import AgentUnderstanding, ExecutiveAgentResult
from app.core.config import Settings
from app.workspace.manager import WorkspaceManager
from app.workspace.repositories.workspace_repository import InMemoryWorkspaceRepository
from app.workspace.service import WorkspaceService
from tests.test_telegram_product_ux import FakeArtifactDelivery, FakeContinuation, StreamableFakeRuntime, build_flow
from tests.test_telegram_production_stabilization import FakeExecutiveAgent


@pytest.fixture
def workspace_service() -> WorkspaceService:
    return WorkspaceService(WorkspaceManager(InMemoryWorkspaceRepository()))


@pytest.fixture
def session_manager(workspace_service: WorkspaceService) -> TelegramSessionManager:
    return TelegramSessionManager(workspace_service=workspace_service, bindings={})


@pytest.fixture
def sender() -> InMemoryTelegramSender:
    return InMemoryTelegramSender()


@pytest.fixture
def conversation_store() -> TelegramConversationStore:
    return TelegramConversationStore()


def _request(text: str) -> TelegramExecutionRequest:
    return TelegramExecutionRequest(
        user_input=text,
        telegram_user_id=777,
        telegram_chat_id=555,
        telegram_message_id=42,
    )


@pytest.mark.asyncio
async def test_conversation_store_singleton_survives_adapter_rebuild(
    workspace_service: WorkspaceService,
) -> None:
    store = get_conversation_store_singleton()
    settings = Settings(telegram_enabled=True, telegram_bot_token="")
    runtime = StreamableFakeRuntime(final_state={"execution_id": "e1", "status": "completed"})

    adapter_a = create_telegram_adapter(
        runtime=runtime,  # type: ignore[arg-type]
        workspace_service=workspace_service,
        settings=settings,
        sender=InMemoryTelegramSender(),
        conversation_store=store,
    )
    convo = await adapter_a.conversation_store.get_or_create(777, 555)
    convo.flow_mode = TelegramFlowMode.PENDING_CLARIFICATION
    convo.last_user_input = "Сделай КП"
    await adapter_a.conversation_store.save(convo)

    adapter_b = create_telegram_adapter(
        runtime=runtime,  # type: ignore[arg-type]
        workspace_service=workspace_service,
        settings=settings,
        sender=InMemoryTelegramSender(),
        conversation_store=store,
    )
    restored = await adapter_b.conversation_store.get(777)
    assert restored is not None
    assert restored.flow_mode == TelegramFlowMode.PENDING_CLARIFICATION
    assert restored.last_user_input == "Сделай КП"
    assert adapter_a.conversation_store is adapter_b.conversation_store


@pytest.mark.asyncio
async def test_session_reused_across_resolves(workspace_service: WorkspaceService) -> None:
    manager = TelegramSessionManager(workspace_service=workspace_service, bindings={})
    first = await manager.resolve(42)
    second = await manager.resolve(42)
    assert first["workspace_id"] == second["workspace_id"]
    assert first["active_session_id"] == second["active_session_id"]
    assert first["active_session_id"] is not None


@pytest.mark.asyncio
async def test_chat_respond_keeps_revision_context(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    runtime = StreamableFakeRuntime(
        final_state={
            "execution_id": "exec-doc",
            "status": "completed",
            "render_result": {"artifact_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"},
            "document_ast": {"root": {"node_type": "document", "children": []}, "node_count": 1},
            "quality_check": {"passed": True, "score": 0.9},
        }
    )
    executive = FakeExecutiveAgent(action="EXECUTE")
    flow = build_flow(runtime, session_manager, sender, conversation_store, continuation=FakeContinuation())
    flow._executive_agent = executive  # type: ignore[assignment]

    await flow.handle_message(_request("Сделай КП для Acme по SEO на 150к"))
    convo = await conversation_store.get(777)
    assert convo is not None
    assert convo.flow_mode == TelegramFlowMode.COMPLETED
    assert convo.last_agent_state is not None

    chat_executive = FakeExecutiveAgent(action="RESPOND", response_message="Пожалуйста!")
    flow._executive_agent = chat_executive  # type: ignore[assignment]
    await flow.handle_message(_request("Спасибо"))

    convo = await conversation_store.get(777)
    assert convo is not None
    assert convo.last_agent_state is not None
    assert convo.flow_mode == TelegramFlowMode.COMPLETED
    assert convo.last_agent_state.get("render_result", {}).get("artifact_id")


@pytest.mark.asyncio
async def test_clarification_stays_pending_on_repeated_ask(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    runtime = StreamableFakeRuntime(
        final_state={
            "execution_id": "exec-kp",
            "status": "completed",
            "result": {"message": "КП готово"},
            "quality_check": {"passed": True},
        }
    )
    executive = FakeExecutiveAgent(
        action="ASK_CLARIFICATION",
        clarification_question="Для какого клиента?",
        goal="Сделай коммерческое предложение",
        missing_information=["клиент", "оффер"],
    )
    flow = build_flow(runtime, session_manager, sender, conversation_store)
    flow._executive_agent = executive  # type: ignore[assignment]

    await flow.handle_message(_request("Сделай коммерческое предложение"))
    result = await flow.handle_message(_request("Клиент Acme, оффер SEO-аудит"))

    assert result.get("resumed_from_clarification") is not True
    assert result["status"] == "clarification"
    assert runtime.calls == []
    convo = await conversation_store.get(777)
    assert convo is not None
    assert convo.pending_clarification is not None
    assert convo.flow_mode == TelegramFlowMode.PENDING_CLARIFICATION


@pytest.mark.asyncio
async def test_clarification_merge_on_execute_after_answer(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    runtime = StreamableFakeRuntime(
        final_state={
            "execution_id": "exec-kp",
            "status": "completed",
            "result": {"message": "КП готово"},
            "quality_check": {"passed": True},
        }
    )

    class ClarifyThenExecute:
        def __init__(self) -> None:
            self.calls = 0

        async def analyze(self, state) -> ExecutiveAgentResult:
            self.calls += 1
            if self.calls == 1:
                return ExecutiveAgentResult(
                    understanding=AgentUnderstanding(
                        goal="Сделай коммерческое предложение",
                        summary="need details",
                        missing_information=["клиент", "оффер"],
                        next_action="request_information",
                    ),
                    decision=AgentDecision(
                        action=DecisionType.ASK_CLARIFICATION,
                        reasoning="missing",
                        clarification_question="Для какого клиента?",
                    ),
                )
            return ExecutiveAgentResult(
                understanding=AgentUnderstanding(
                    goal="Сделай коммерческое предложение",
                    summary="ready",
                    next_action="execute",
                    required_capabilities=["document_generation"],
                ),
                decision=AgentDecision(
                    action=DecisionType.EXECUTE,
                    reasoning="enough info",
                ),
            )

    flow = build_flow(runtime, session_manager, sender, conversation_store)
    flow._executive_agent = ClarifyThenExecute()  # type: ignore[assignment]

    await flow.handle_message(_request("Сделай коммерческое предложение"))
    result = await flow.handle_message(_request("Клиент Acme, оффер SEO-аудит"))

    assert result.get("resumed_from_clarification") is True
    assert "коммерческое предложение" in result["merged_input"].lower() or "Сделай" in result["merged_input"]
    assert "Acme" in result["merged_input"]
    assert runtime.calls
    assert "Acme" in runtime.calls[0]["user_input"]


@pytest.mark.asyncio
async def test_topic_switch_from_clarification_to_chat(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    runtime = StreamableFakeRuntime(final_state={"execution_id": "should-not-run", "status": "completed"})

    class SwitchingExecutive:
        def __init__(self) -> None:
            self.calls = 0

        async def analyze(self, state) -> ExecutiveAgentResult:
            self.calls += 1
            if self.calls == 1:
                return ExecutiveAgentResult(
                    understanding=AgentUnderstanding(
                        goal="Сделай презентацию",
                        summary="need details",
                        missing_information=["тема"],
                        next_action="request_information",
                    ),
                    decision=AgentDecision(
                        action=DecisionType.ASK_CLARIFICATION,
                        reasoning="missing topic",
                        clarification_question="Какая тема презентации?",
                    ),
                )
            return ExecutiveAgentResult(
                understanding=AgentUnderstanding(goal="поздороваться", summary="chat", next_action="respond"),
                decision=AgentDecision(
                    action=DecisionType.RESPOND,
                    reasoning="topic switch",
                    response_message="Привет! Чем ещё помочь?",
                ),
            )

    executive = SwitchingExecutive()
    flow = build_flow(runtime, session_manager, sender, conversation_store)
    flow._executive_agent = executive  # type: ignore[assignment]

    await flow.handle_message(_request("Сделай презентацию"))
    result = await flow.handle_message(_request("Привет"))

    assert result["intent"] == "chat"
    assert runtime.calls == []
    convo = await conversation_store.get(777)
    assert convo is not None
    assert convo.pending_clarification is None


@pytest.mark.asyncio
async def test_revision_uses_prior_artifact_after_chat(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    runtime = StreamableFakeRuntime(
        final_state={
            "execution_id": "exec-doc",
            "status": "completed",
            "render_result": {"artifact_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"},
            "document_ast": {"root": {"node_type": "document", "children": []}, "node_count": 1},
            "quality_check": {"passed": True, "score": 0.95},
        }
    )
    continuation = FakeContinuation()
    flow = build_flow(
        runtime,
        session_manager,
        sender,
        conversation_store,
        continuation=continuation,
        executive_agent=FakeExecutiveAgent(action="EXECUTE"),
    )

    await flow.handle_message(_request("Создай SWOT для CoffeeLab"))
    flow._executive_agent = FakeExecutiveAgent(action="RESPOND", response_message="Ок")  # type: ignore[assignment]
    await flow.handle_message(_request("Спасибо"))

    convo = await conversation_store.get(777)
    assert convo is not None
    assert convo.last_agent_state is not None

    revised = await flow.handle_callback(
        TelegramCallbackRequest(
            action="revise",
            telegram_user_id=777,
            telegram_chat_id=555,
            callback_query_id="cb1",
            callback_data="tg:revise",
        )
    )
    assert revised["status"] == "revision_prompted"

    # C1: after revise prompt, Executive DecisionType routes to execution (not capability fork).
    flow._executive_agent = FakeExecutiveAgent(action="EXECUTE")  # type: ignore[assignment]
    feedback = await flow.handle_message(_request("Сделай короче и добавь CTA"))
    assert feedback["status"] == "completed"
    assert runtime.calls
    assert len(runtime.calls) >= 2


@pytest.mark.asyncio
async def test_workspace_history_appended_for_dialogue(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
    workspace_service: WorkspaceService,
) -> None:
    runtime = StreamableFakeRuntime(final_state={"execution_id": "e", "status": "completed"})
    flow = build_flow(
        runtime,
        session_manager,
        sender,
        conversation_store,
        executive_agent=FakeExecutiveAgent(action="RESPOND", response_message="Привет!"),
    )
    await flow.handle_message(_request("Привет"))

    snapshot = await session_manager.resolve(777)
    conversation = snapshot.get("conversation") or {}
    # Snapshot may be stale; reload from manager.
    from uuid import UUID

    session_id = snapshot["active_session_id"]
    conv = await workspace_service.manager.get_conversation_by_session(UUID(session_id))
    assert conv is not None
    roles = [message.get("role") for message in conv.messages]
    assert "user" in roles
    assert "assistant" in roles


@pytest.mark.asyncio
async def test_running_busy_gate_blocks_second_pipeline(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    runtime = StreamableFakeRuntime(final_state={"execution_id": "e", "status": "completed"})
    flow = build_flow(
        runtime,
        session_manager,
        sender,
        conversation_store,
        executive_agent=FakeExecutiveAgent(action="EXECUTE"),
    )
    convo = await conversation_store.get_or_create(777, 555)
    convo.flow_mode = TelegramFlowMode.RUNNING
    await conversation_store.save(convo)

    result = await flow.handle_message(_request("ещё одна задача"))

    assert result["status"] == "busy"
    assert "Ещё работаю" in result["reply"]
    assert runtime.calls == []


@pytest.mark.asyncio
async def test_allowlist_none_accepts_all(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    runtime = StreamableFakeRuntime(
        final_state={
            "execution_id": "e",
            "status": "completed",
            "decision": {"action": "RESPOND", "response_message": "ok"},
            "result": {"message": "ok"},
        }
    )
    flow = TelegramProductFlow(
        runtime=runtime,  # type: ignore[arg-type]
        session_manager=session_manager,
        sender=sender,
        conversation_store=conversation_store,
        progress_messenger=TelegramProgressMessenger(sender),
        continuation=FakeContinuation(),
        artifact_delivery=FakeArtifactDelivery(),
        executive_agent=FakeExecutiveAgent(action="RESPOND"),
        allowed_user_ids=None,
    )
    result = await flow.handle_message(_request("привет"))
    assert result["status"] != "forbidden"


@pytest.mark.asyncio
async def test_allowlist_empty_set_denies_all(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    runtime = StreamableFakeRuntime(final_state={"execution_id": "e", "status": "completed"})
    flow = TelegramProductFlow(
        runtime=runtime,  # type: ignore[arg-type]
        session_manager=session_manager,
        sender=sender,
        conversation_store=conversation_store,
        progress_messenger=TelegramProgressMessenger(sender),
        continuation=FakeContinuation(),
        artifact_delivery=FakeArtifactDelivery(),
        executive_agent=FakeExecutiveAgent(action="RESPOND"),
        allowed_user_ids=set(),
    )
    result = await flow.handle_message(_request("привет"))
    assert result["status"] == "forbidden"
    assert "Доступ ограничен" in result["reply"]
    assert runtime.calls == []


@pytest.mark.asyncio
async def test_allowlist_nonempty_filters_users(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    runtime = StreamableFakeRuntime(final_state={"execution_id": "e", "status": "completed"})
    flow = TelegramProductFlow(
        runtime=runtime,  # type: ignore[arg-type]
        session_manager=session_manager,
        sender=sender,
        conversation_store=conversation_store,
        progress_messenger=TelegramProgressMessenger(sender),
        continuation=FakeContinuation(),
        artifact_delivery=FakeArtifactDelivery(),
        executive_agent=FakeExecutiveAgent(action="RESPOND"),
        allowed_user_ids={111},
    )
    denied = await flow.handle_message(_request("привет"))
    assert denied["status"] == "forbidden"
    assert runtime.calls == []


@pytest.mark.asyncio
async def test_incomplete_delivery_without_artifact_or_text(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    """M2: completed without artifacts/result text → incomplete, not silent «Готово»."""
    from app.conversation.messages import INCOMPLETE_REASON

    runtime = StreamableFakeRuntime(
        final_state={
            "execution_id": "exec-empty",
            "status": "completed",
        }
    )
    flow = build_flow(
        runtime,
        session_manager,
        sender,
        conversation_store,
        executive_agent=FakeExecutiveAgent(action="EXECUTE"),
    )
    result = await flow.handle_message(_request("Сделай КП"))
    assert result["status"] == "incomplete"
    assert INCOMPLETE_REASON in (result.get("reply") or "")
    assert "Готово" not in (result.get("reply") or "")
    convo = await conversation_store.get(777)
    assert convo is not None
    assert convo.flow_mode == TelegramFlowMode.FAILED


@pytest.mark.asyncio
async def test_waiting_user_revision_without_artifact_is_incomplete(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    """Do not leak understanding.summary when quality asks for user after empty render."""
    from app.conversation.messages import INCOMPLETE_REASON

    runtime = StreamableFakeRuntime(
        final_state={
            "execution_id": "exec-wait-empty",
            "status": "waiting_user_revision",
            "understanding": {
                "summary": (
                    "Пользователь запрашивает коммерческое предложение "
                    "для компании Acme на услугу SEO-аудита."
                ),
                "goal": "КП Acme",
            },
            "revision_count": 1,
        }
    )
    flow = build_flow(
        runtime,
        session_manager,
        sender,
        conversation_store,
        executive_agent=FakeExecutiveAgent(action="EXECUTE"),
    )
    result = await flow.handle_message(_request("Сделай КП для Acme"))
    assert result["status"] == "incomplete"
    reply = result.get("reply") or ""
    assert INCOMPLETE_REASON in reply
    assert "Пользователь запрашивает" not in reply
    convo = await conversation_store.get(777)
    assert convo is not None
    assert convo.flow_mode == TelegramFlowMode.FAILED


@pytest.mark.asyncio
async def test_revision_prompted_routes_via_executive_not_blind_feedback(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    """M3: after revise prompt, chat/new-task go through Executive — not blind continuation."""
    continuation = FakeContinuation()
    runtime = StreamableFakeRuntime(
        final_state={
            "execution_id": "exec-rev-m3",
            "status": "completed",
            "result": {"message": "Новая задача выполнена."},
        }
    )
    flow = build_flow(
        runtime,
        session_manager,
        sender,
        conversation_store,
        continuation=continuation,
        executive_agent=FakeExecutiveAgent(action="RESPOND", response_message="Ок, понял."),
    )
    convo = await conversation_store.get_or_create(777, 555)
    convo.flow_mode = TelegramFlowMode.REVISION_PROMPTED
    convo.last_agent_state = {
        "status": "completed",
        "render_result": {"artifact_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"},
    }
    await conversation_store.save(convo)

    chat = await flow.handle_message(_request("Спасибо, пока не надо"))
    assert chat["status"] == "completed"
    assert continuation.calls == []
    assert runtime.calls == []
    convo = await conversation_store.get(777)
    assert convo is not None
    assert convo.flow_mode == TelegramFlowMode.COMPLETED

    convo.flow_mode = TelegramFlowMode.REVISION_PROMPTED
    await conversation_store.save(convo)
    flow._executive_agent = FakeExecutiveAgent(action="EXECUTE")  # type: ignore[assignment]
    task = await flow.handle_message(_request("Сделай другое КП"))
    assert task["status"] == "completed"
    assert continuation.calls == []
    assert runtime.calls


def test_factory_production_empty_allowlist_is_deny_all(workspace_service: WorkspaceService) -> None:
    settings = Settings(
        app_env="production",
        telegram_enabled=True,
        telegram_bot_token="",
        telegram_allowed_user_ids="",
    )
    adapter = create_telegram_adapter(
        runtime=StreamableFakeRuntime(final_state={}),  # type: ignore[arg-type]
        workspace_service=workspace_service,
        settings=settings,
        sender=InMemoryTelegramSender(),
        redis_client=object(),
    )
    assert adapter._allowed_user_ids == set()


def test_factory_dev_empty_allowlist_is_none(workspace_service: WorkspaceService) -> None:
    settings = Settings(
        app_env="development",
        telegram_enabled=True,
        telegram_bot_token="",
        telegram_allowed_user_ids="",
    )
    adapter = create_telegram_adapter(
        runtime=StreamableFakeRuntime(final_state={}),  # type: ignore[arg-type]
        workspace_service=workspace_service,
        settings=settings,
        sender=InMemoryTelegramSender(),
        redis_client=object(),
    )
    assert adapter._allowed_user_ids is None