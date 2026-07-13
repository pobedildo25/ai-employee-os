from __future__ import annotations

from typing import Any

import pytest

from app.adapters.telegram.flow import TelegramProductFlow
from app.adapters.telegram.models import TelegramExecutionRequest
from app.adapters.telegram.progress import TelegramProgressMessenger
from app.adapters.telegram.sender import InMemoryTelegramSender
from app.adapters.telegram.session import TelegramSessionManager
from app.agents.decision.models import AgentDecision, DecisionType
from app.agents.executive.models import AgentUnderstanding, ExecutiveAgentResult
from app.adapters.telegram.conversation_store import TelegramConversationStore
from app.workspace.manager import WorkspaceManager
from app.workspace.repositories.workspace_repository import InMemoryWorkspaceRepository
from app.workspace.service import WorkspaceService
from tests.test_telegram_product_ux import FakeArtifactDelivery, StreamableFakeRuntime, build_flow


class FakeExecutiveAgent:
    def __init__(self, *, action: str, response_message: str = "") -> None:
        self.action = action
        self.response_message = response_message
        self.calls: list[dict[str, Any]] = []

    async def analyze(self, state) -> ExecutiveAgentResult:
        self.calls.append({"user_input": state.get("user_input")})
        return ExecutiveAgentResult(
            understanding=AgentUnderstanding(
                goal=state.get("user_input", ""),
                summary="classified",
                next_action="respond" if self.action == "RESPOND" else "execute",
            ),
            decision=AgentDecision(
                action=DecisionType(self.action),
                reasoning="test",
                response_message=self.response_message or None,
            ),
        )


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
async def test_greeting_does_not_start_execution(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    runtime = StreamableFakeRuntime(
        final_state={"execution_id": "exec-should-not-run", "status": "completed"}
    )
    executive = FakeExecutiveAgent(
        action="RESPOND",
        response_message="Привет! Я NOVA, AI-сотрудник агентства.",
    )
    flow = build_flow(
        runtime,
        session_manager,
        sender,
        conversation_store,
        continuation=None,
    )
    flow._executive_agent = executive  # type: ignore[assignment]

    result = await flow.handle_message(_request("Привет"))

    assert result["intent"] == "chat"
    assert runtime.calls == []
    assert executive.calls and executive.calls[0]["user_input"] == "Привет"
    assert sender.sent[-1]["text"] == "Привет! Я NOVA, AI-сотрудник агентства."
    assert sender.sent[0]["text"] != "Думаю…"


@pytest.mark.asyncio
async def test_capabilities_question_does_not_start_execution(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    runtime = StreamableFakeRuntime(final_state={"execution_id": "exec-skip", "status": "completed"})
    executive = FakeExecutiveAgent(
        action="RESPOND",
        response_message="Я помогаю готовить КП, презентации и стратегии.",
    )
    flow = build_flow(runtime, session_manager, sender, conversation_store)
    flow._executive_agent = executive  # type: ignore[assignment]

    result = await flow.handle_message(_request("Что умеешь?"))

    assert result["intent"] == "chat"
    assert runtime.calls == []
    assert "КП" in sender.sent[-1]["text"]


@pytest.mark.asyncio
async def test_task_request_starts_execution_pipeline(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    runtime = StreamableFakeRuntime(
        final_state={
            "execution_id": "exec-task",
            "status": "completed",
            "result": {"message": "Презентация готова."},
            "quality_check": {"passed": True, "score": 0.9},
        }
    )
    executive = FakeExecutiveAgent(action="EXECUTE")
    flow = build_flow(runtime, session_manager, sender, conversation_store, continuation=None)
    flow._executive_agent = executive  # type: ignore[assignment]

    result = await flow.handle_message(_request("Создай презентацию"))

    assert result.get("intent") != "chat"
    assert len(runtime.calls) == 1
    assert runtime.calls[0]["mode"] == "stream"
    assert runtime.calls[0]["user_input"] == "Создай презентацию"
    # Single-step EXECUTE skips ephemeral progress theater.
    assert all(item["text"] != "Думаю…" for item in sender.sent)


@pytest.mark.asyncio
async def test_task_execution_preserves_telegram_progress_ux(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    runtime = StreamableFakeRuntime(
        final_state={
            "execution_id": "exec-progress",
            "status": "completed",
            "result": {"message": "Готово."},
            "quality_check": {"passed": True, "score": 0.91},
        },
        stream_events=[
            {
                "orchestration": {
                    "telegram_progress": {
                        "progress_percent": 40,
                        "lines": [{"title": "Стратегия", "status_icon": "⏳", "status_label": "выполняется"}],
                    }
                }
            }
        ],
    )
    executive = FakeExecutiveAgent(action="CREATE_PLAN")
    flow = TelegramProductFlow(
        runtime=runtime,  # type: ignore[arg-type]
        session_manager=session_manager,
        sender=sender,
        conversation_store=conversation_store,
        progress_messenger=TelegramProgressMessenger(sender, min_interval_seconds=0.0),
        artifact_delivery=FakeArtifactDelivery(),  # type: ignore[arg-type]
        executive_agent=executive,  # type: ignore[arg-type]
    )

    await flow.handle_message(_request("Подготовь стратегию"))

    assert runtime.calls
    assert sender.sent[0]["text"] == "Думаю…"
    assert sender.edited
    assert sender.deleted
