"""Sprint E — slash commands (/new, /status, /cancel, /start)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.adapters.telegram.conversation_store import TelegramConversationStore, TelegramFlowMode
from app.adapters.telegram.models import TelegramExecutionRequest
from app.adapters.telegram.sender import InMemoryTelegramSender
from app.adapters.telegram.session import TelegramSessionManager
from app.conversation.commands import SlashCommand, parse_slash_command
from app.conversation.messages import (
    format_slash_cancelled,
    format_slash_new_confirm,
    format_slash_nothing_to_cancel,
    format_slash_start,
    format_slash_status,
)
from app.conversation.models import ConversationState, FlowMode
from app.conversation.store import ConversationStore
from app.workspace.manager import WorkspaceManager
from app.workspace.repositories.workspace_repository import InMemoryWorkspaceRepository
from app.workspace.service import WorkspaceService
from tests.test_telegram_chat_vs_task import FakeExecutiveAgent
from tests.test_telegram_product_ux import StreamableFakeRuntime, build_flow


@pytest.fixture
def session_manager() -> TelegramSessionManager:
    return TelegramSessionManager(
        workspace_service=WorkspaceService(WorkspaceManager(InMemoryWorkspaceRepository())),
        bindings={},
    )


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


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("/new", SlashCommand.NEW),
        ("/STATUS", SlashCommand.STATUS),
        ("/Cancel@NovaBot", SlashCommand.CANCEL),
        ("/start@bot", SlashCommand.START),
        ("/new please", SlashCommand.NEW),
        ("hello", None),
        ("/newline", None),
        ("", None),
    ],
)
def test_parse_slash_command(text: str, expected: SlashCommand | None) -> None:
    assert parse_slash_command(text) == expected


@pytest.mark.asyncio
async def test_new_resets_dialog_state(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    runtime = StreamableFakeRuntime(final_state={"status": "completed"})
    flow = build_flow(
        runtime,
        session_manager,
        sender,
        conversation_store,
        executive_agent=FakeExecutiveAgent(action="RESPOND", response_message="hi"),
    )
    convo = await conversation_store.get_or_create(777, 555)
    convo.flow_mode = TelegramFlowMode.COMPLETED
    convo.last_agent_state = {"status": "completed"}
    convo.artifact_ids = ["art-1"]
    convo.last_execution_id = "exec-old"
    convo.progress_message_id = 99
    await conversation_store.save(convo)

    result = await flow.handle_message(_request("/new"))

    assert result["command"] == "new"
    assert result["reply"] == format_slash_new_confirm()
    restored = await conversation_store.get(777)
    assert restored is not None
    assert restored.flow_mode == TelegramFlowMode.IDLE
    assert restored.last_agent_state is None
    assert restored.artifact_ids == []
    assert restored.last_execution_id is None
    assert restored.progress_message_id is None
    assert runtime.calls == []


@pytest.mark.asyncio
async def test_status_reports_mode(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    runtime = StreamableFakeRuntime(final_state={"status": "completed"})
    flow = build_flow(
        runtime,
        session_manager,
        sender,
        conversation_store,
        executive_agent=FakeExecutiveAgent(action="RESPOND"),
    )
    convo = await conversation_store.get_or_create(777, 555)
    convo.flow_mode = TelegramFlowMode.WAITING_APPROVAL
    convo.last_execution_id = "exec-42"
    convo.artifact_ids = ["a1"]
    await conversation_store.save(convo)

    result = await flow.handle_message(_request("/status"))

    assert result["command"] == "status"
    assert "жду подтверждения" in result["reply"]
    assert "да" in result["reply"]
    assert "exec-42" in result["reply"]
    assert runtime.calls == []


@pytest.mark.asyncio
async def test_cancel_during_running(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    runtime = StreamableFakeRuntime(final_state={"status": "completed"})
    flow = build_flow(
        runtime,
        session_manager,
        sender,
        conversation_store,
        executive_agent=FakeExecutiveAgent(action="EXECUTE"),
    )
    convo = await conversation_store.get_or_create(777, 555)
    convo.flow_mode = TelegramFlowMode.RUNNING
    convo.last_execution_id = "exec-run"
    await conversation_store.save(convo)

    result = await flow.handle_message(_request("/cancel"))

    assert result["status"] == "cancelled"
    assert result["reply"] == format_slash_cancelled()
    restored = await conversation_store.get(777)
    assert restored is not None
    assert restored.flow_mode == TelegramFlowMode.IDLE
    assert runtime.calls == []


@pytest.mark.asyncio
async def test_cancel_when_idle(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    runtime = StreamableFakeRuntime(final_state={"status": "completed"})
    flow = build_flow(
        runtime,
        session_manager,
        sender,
        conversation_store,
        executive_agent=FakeExecutiveAgent(action="RESPOND"),
    )

    result = await flow.handle_message(_request("/cancel"))

    assert result["command"] == "cancel"
    assert result["reply"] == format_slash_nothing_to_cancel()
    assert runtime.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("command", ["/cancel", "/status", "/new"])
async def test_commands_work_while_flow_running(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
    command: str,
) -> None:
    runtime = StreamableFakeRuntime(final_state={"status": "completed"})
    flow = build_flow(
        runtime,
        session_manager,
        sender,
        conversation_store,
        executive_agent=FakeExecutiveAgent(action="EXECUTE"),
    )
    convo = await conversation_store.get_or_create(777, 555)
    convo.flow_mode = TelegramFlowMode.RUNNING
    convo.last_execution_id = "exec-busy"
    await conversation_store.save(convo)

    result = await flow.handle_message(_request(command))

    assert result.get("status") != "busy"
    assert "Ещё работаю" not in str(result.get("reply") or "")
    assert runtime.calls == []


@pytest.mark.asyncio
async def test_start_lists_commands_and_limits(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    runtime = StreamableFakeRuntime(final_state={"status": "completed"})
    flow = build_flow(
        runtime,
        session_manager,
        sender,
        conversation_store,
        executive_agent=FakeExecutiveAgent(action="RESPOND"),
    )

    result = await flow.handle_message(_request("/start"))

    assert result["command"] == "start"
    assert result["reply"] == format_slash_start()
    assert "/new" in result["reply"]
    assert "research" in result["reply"].lower() or "web" in result["reply"].lower()
    assert runtime.calls == []


@pytest.mark.asyncio
async def test_cancel_concurrent_with_running_execution(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    """Lock is released during stream so /cancel can interrupt RUNNING."""

    class SlowRuntime:
        def __init__(self) -> None:
            self.started = asyncio.Event()
            self.calls: list[dict[str, Any]] = []

        async def stream(self, user_input: str, *, trace_id=None, context=None, metadata=None):
            self.calls.append({"mode": "stream", "user_input": user_input})
            self.started.set()
            await asyncio.sleep(0.3)
            yield {
                "executor": {
                    "execution_id": "exec-slow",
                    "status": "completed",
                    "result": {"message": "should not deliver"},
                }
            }

        async def execute(self, *args, **kwargs):
            raise AssertionError("execute should not be used")

    runtime = SlowRuntime()
    flow = build_flow(
        runtime,  # type: ignore[arg-type]
        session_manager,
        sender,
        conversation_store,
        executive_agent=FakeExecutiveAgent(action="CREATE_PLAN"),
    )

    task = asyncio.create_task(flow.handle_message(_request("Сложная стратегия")))
    await runtime.started.wait()
    cancel_result = await flow.handle_message(_request("/cancel"))
    exec_result = await task

    assert cancel_result["status"] == "cancelled"
    assert exec_result["status"] == "cancelled"
    restored = await conversation_store.get(777)
    assert restored is not None
    assert restored.flow_mode == TelegramFlowMode.IDLE
    assert not any(
        item.get("text") == "should not deliver" for item in sender.sent
    )


@pytest.mark.asyncio
async def test_reset_dialog_on_store() -> None:
    store = ConversationStore()
    state = await store.get_or_create(1, 10)
    state.flow_mode = FlowMode.COMPLETED
    state.last_agent_state = {"x": 1}
    state.artifact_ids = ["a"]
    state.last_execution_id = "e"
    state.progress_message_id = 5
    await store.save(state)

    await store.reset_dialog(1)
    loaded = await store.get(1)
    assert loaded is not None
    assert loaded.flow_mode == FlowMode.IDLE
    assert loaded.last_agent_state is None
    assert loaded.artifact_ids == []
    assert format_slash_status(
        ConversationState(user_id=1, chat_id=10, flow_mode=FlowMode.IDLE)
    )
