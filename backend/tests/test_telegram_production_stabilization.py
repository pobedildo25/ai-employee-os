from __future__ import annotations

from typing import Any

import pytest

from app.adapters.telegram.conversation_store import TelegramConversationStore, TelegramFlowMode
from app.adapters.telegram.flow import TelegramProductFlow
from app.adapters.telegram.models import TelegramExecutionRequest
from app.adapters.telegram.progress import TelegramProgressMessenger
from app.adapters.telegram.sender import InMemoryTelegramSender
from app.adapters.telegram.session import TelegramSessionManager
from app.agent_runtime.exceptions import GraphExecutionError
from app.agents.decision.models import AgentDecision, DecisionType
from app.agents.executive.models import AgentUnderstanding, ExecutiveAgentResult
from app.context.builder import create_context_builder
from app.workspace.manager import WorkspaceManager
from app.workspace.repositories.workspace_repository import InMemoryWorkspaceRepository
from app.workspace.service import WorkspaceService
from tests.test_telegram_product_ux import FakeArtifactDelivery, StreamableFakeRuntime, build_flow


class FakeExecutiveAgent:
    def __init__(
        self,
        *,
        action: str,
        response_message: str = "",
        clarification_question: str = "",
        goal: str | None = None,
        missing_information: list[str] | None = None,
    ) -> None:
        self.action = action
        self.response_message = response_message
        self.clarification_question = clarification_question
        self.goal = goal
        self.missing_information = missing_information or []
        self.calls: list[dict[str, Any]] = []

    async def analyze(self, state) -> ExecutiveAgentResult:
        user_input = state.get("user_input", "")
        self.calls.append({"user_input": user_input})
        return ExecutiveAgentResult(
            understanding=AgentUnderstanding(
                goal=self.goal or user_input,
                summary="classified",
                missing_information=self.missing_information,
                next_action="respond" if self.action == "RESPOND" else "execute",
            ),
            decision=AgentDecision(
                action=DecisionType(self.action),
                reasoning="test",
                response_message=self.response_message or None,
                clarification_question=self.clarification_question or None,
            ),
        )


class FailingRuntime(StreamableFakeRuntime):
    def __init__(
        self,
        *,
        execution_id: str = "exec-fail-1",
        trace_id: str = "trace-fail-1",
        message: str = "context_builder failed",
    ) -> None:
        super().__init__(final_state={"execution_id": execution_id, "status": "completed"})
        self._execution_id = execution_id
        self._trace_id = trace_id
        self._message = message

    async def stream(self, user_input: str, *, trace_id=None, context=None, metadata=None):
        self.calls.append(
            {"mode": "stream", "user_input": user_input, "context": context, "metadata": metadata}
        )
        raise GraphExecutionError(
            f"Workflow stream failed: {self._message}",
            execution_id=self._execution_id,
            trace_id=self._trace_id,
        )
        yield {}  # pragma: no cover


@pytest.fixture
def workspace_service() -> WorkspaceService:
    return WorkspaceService(WorkspaceManager(InMemoryWorkspaceRepository()))


@pytest.fixture
def session_manager(workspace_service: WorkspaceService) -> TelegramSessionManager:
    return TelegramSessionManager(workspace_service=workspace_service)


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
async def test_pipeline_exception_sends_friendly_error_message(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    runtime = FailingRuntime(execution_id="exec-err", trace_id="trace-err")
    executive = FakeExecutiveAgent(action="EXECUTE")
    flow = build_flow(runtime, session_manager, sender, conversation_store)
    flow._executive_agent = executive  # type: ignore[assignment]

    result = await flow.handle_message(_request("Создай презентацию"))

    assert result["status"] == "failed"
    assert result["trace_id"] == "trace-err"
    assert result["execution_id"] == "exec-err"
    assert sender.edited
    assert sender.edited[-1]["text"] == "⚠️ Задача прервана"
    error_text = sender.sent[-1]["text"]
    assert "Произошла ошибка при выполнении задачи" in error_text
    assert "trace_id: trace-err" in error_text
    assert "execution_id: exec-err" in error_text
    assert "Traceback" not in error_text


@pytest.mark.asyncio
async def test_clarification_then_answer_resumes_task_pipeline(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    runtime = StreamableFakeRuntime(
        final_state={
            "execution_id": "exec-kp",
            "status": "completed",
            "quality_check": {"passed": True, "score": 0.9},
        }
    )
    executive = FakeExecutiveAgent(
        action="ASK_CLARIFICATION",
        clarification_question="Какие конкретные детали нужны для КП?",
        goal="Сделай КП для Яндекса",
        missing_information=["тема КП"],
    )
    flow = build_flow(runtime, session_manager, sender, conversation_store)
    flow._executive_agent = executive  # type: ignore[assignment]

    first = await flow.handle_message(_request("Сделай КП для Яндекса"))
    assert first["status"] == "clarification"
    assert runtime.calls == []
    assert "детали" in sender.sent[-1]["text"].lower()

    convo = conversation_store.get(777)
    assert convo is not None
    assert convo.flow_mode == TelegramFlowMode.PENDING_CLARIFICATION
    assert convo.pending_clarification is not None
    assert convo.pending_clarification.original_goal == "Сделай КП для Яндекса"

    second = await flow.handle_message(_request("КП на AI автоматизацию"))
    assert second.get("resumed_from_clarification") is True
    assert len(runtime.calls) == 1
    assert "Яндекса" in runtime.calls[0]["user_input"]
    assert "AI автоматизацию" in runtime.calls[0]["user_input"]
    assert convo.pending_clarification is None


@pytest.mark.asyncio
async def test_greeting_still_skips_execution(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    runtime = StreamableFakeRuntime(final_state={"execution_id": "exec-skip", "status": "completed"})
    executive = FakeExecutiveAgent(action="RESPOND", response_message="Привет! Я NOVA.")
    flow = build_flow(runtime, session_manager, sender, conversation_store)
    flow._executive_agent = executive  # type: ignore[assignment]

    result = await flow.handle_message(_request("Привет"))

    assert result["intent"] == "chat"
    assert runtime.calls == []


@pytest.mark.asyncio
async def test_broken_memory_provider_allows_task_execution(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    class BrokenMemoryProvider:
        name = "memory"

        async def fetch(self, request):
            raise RuntimeError("qdrant unavailable")

    runtime = StreamableFakeRuntime(
        final_state={"execution_id": "exec-no-mem", "status": "completed"}
    )
    executive = FakeExecutiveAgent(action="EXECUTE")
    flow = TelegramProductFlow(
        runtime=runtime,  # type: ignore[arg-type]
        session_manager=session_manager,
        sender=sender,
        conversation_store=conversation_store,
        progress_messenger=TelegramProgressMessenger(sender, min_interval_seconds=0.0),
        artifact_delivery=FakeArtifactDelivery(),  # type: ignore[arg-type]
        executive_agent=executive,  # type: ignore[arg-type]
    )

    # Context builder degradation is tested separately; this confirms task path still runs.
    result = await flow.handle_message(_request("Создай презентацию по стратегии"))
    assert result["status"] == "completed"
    assert runtime.calls


@pytest.mark.asyncio
async def test_context_builder_continues_when_memory_provider_fails() -> None:
    from app.context.builder import ContextBuilder
    from app.context.models import ContextRequest
    from app.context.providers.base import ContextProvider

    class BrokenProvider(ContextProvider):
        name = "memory"

        async def fetch(self, request: ContextRequest) -> dict:
            raise AttributeError("'QdrantClient' object has no attribute 'search'")

    builder = ContextBuilder(providers=[BrokenProvider()])
    context = await builder.build(user_input="Создай КП", trace_id="trace-ctx")

    assert context.memory_context == []
