from typing import Any
from uuid import uuid4

import pytest

from app.adapters.telegram.bot import TelegramAdapter
from app.adapters.telegram.conversation_store import TelegramConversationStore, TelegramFlowMode
from app.adapters.telegram.flow import TelegramProductFlow
from app.adapters.telegram.handlers import TelegramMessageHandler
from app.adapters.telegram.mapper import TelegramMapper
from app.adapters.telegram.models import TelegramCallbackRequest, TelegramExecutionRequest
from app.adapters.telegram.presenter import format_approval_message, format_revision_prompt
from app.adapters.telegram.progress import TelegramProgressMessenger
from app.adapters.telegram.revision import is_contextual_revision_message
from app.adapters.telegram.sender import InMemoryTelegramSender
from app.adapters.telegram.session import TelegramSessionManager
from app.agent_runtime.exceptions import GraphExecutionError
from app.agents.decision.models import AgentDecision, DecisionType
from app.agents.executive.models import AgentUnderstanding, ExecutiveAgentResult
from app.orchestration.orchestrator import Orchestrator
from app.orchestration.store import ExecutionStore
from app.workspace.manager import WorkspaceManager
from app.workspace.repositories.workspace_repository import InMemoryWorkspaceRepository
from app.workspace.service import WorkspaceService
from tests.test_telegram_adapter import SAMPLE_UPDATE


SAMPLE_CALLBACK_APPROVE = {
    "update_id": 2001,
    "callback_query": {
        "id": "cb-1",
        "from": {"id": 777, "is_bot": False, "first_name": "Ada"},
        "message": {
            "message_id": 50,
            "chat": {"id": 555, "type": "private"},
            "date": 1710000001,
            "text": "plan",
        },
        "data": "tg:approve",
    },
}


class StreamableFakeRuntime:
    def __init__(self, *, final_state: dict[str, Any], stream_events: list[dict[str, Any]] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._final_state = final_state
        self._stream_events = stream_events or []

    async def execute(self, user_input: str, *, trace_id=None, context=None, metadata=None) -> dict[str, Any]:
        self.calls.append(
            {"mode": "execute", "user_input": user_input, "context": context, "metadata": metadata}
        )
        return self._final_state

    async def stream(self, user_input: str, *, trace_id=None, context=None, metadata=None):
        self.calls.append(
            {"mode": "stream", "user_input": user_input, "context": context, "metadata": metadata}
        )
        for event in self._stream_events:
            yield event
        if not self._stream_events:
            yield {"executor": self._final_state}


class FakeContinuation:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def continue_revision(self, prior_state: dict[str, Any], user_feedback: str) -> dict[str, Any]:
        self.calls.append({"prior_state": prior_state, "user_feedback": user_feedback})
        return {
            **prior_state,
            "status": "completed",
            "revision_result": {
                "status": "COMPLETED",
                "artifact_id": prior_state.get("render_result", {}).get("artifact_id"),
            },
            "quality_check": {"passed": True, "score": 0.95},
            "metadata": {**(prior_state.get("metadata") or {}), "user_feedback": user_feedback},
        }


class FakeArtifactDelivery:
    async def collect_artifacts(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        render = state.get("render_result") or {}
        if render.get("artifact_id"):
            return [
                {
                    "id": render["artifact_id"],
                    "name": "КП.docx",
                    "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "storage_path": "client/project/kp.docx",
                }
            ]
        return []

    async def download(self, artifact: dict[str, Any]) -> bytes | None:
        return b"docx-bytes"


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


def build_flow(
    runtime: StreamableFakeRuntime,
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
    *,
    continuation: FakeContinuation | None = None,
    orchestrator: Orchestrator | None = None,
    executive_agent: Any | None = None,
) -> TelegramProductFlow:
    flow = TelegramProductFlow(
        runtime=runtime,  # type: ignore[arg-type]
        session_manager=session_manager,
        sender=sender,
        conversation_store=conversation_store,
        progress_messenger=TelegramProgressMessenger(sender, min_interval_seconds=0.0),
        continuation=continuation,  # type: ignore[arg-type]
        artifact_delivery=FakeArtifactDelivery(),  # type: ignore[arg-type]
        orchestrator=orchestrator or Orchestrator(store=ExecutionStore()),
        executive_agent=executive_agent,  # type: ignore[arg-type]
    )
    if executive_agent is None:
        flow._executive_agent = _task_executive_agent()  # type: ignore[assignment]
    return flow


def _task_executive_agent() -> Any:
    class TaskExecutive:
        async def analyze(self, state):
            return ExecutiveAgentResult(
                understanding=AgentUnderstanding(
                    goal=state.get("user_input", ""),
                    summary="task",
                    next_action="execute",
                    required_capabilities=["document_generation"],
                ),
                decision=AgentDecision(
                    action=DecisionType.EXECUTE,
                    reasoning="task request",
                ),
            )

    return TaskExecutive()


def _plan_executive_agent() -> Any:
    class PlanExecutive:
        async def analyze(self, state):
            return ExecutiveAgentResult(
                understanding=AgentUnderstanding(
                    goal=state.get("user_input", ""),
                    summary="multi-stage plan",
                    next_action="create_plan",
                    required_capabilities=["research", "strategy", "document_generation"],
                ),
                decision=AgentDecision(
                    action=DecisionType.CREATE_PLAN,
                    reasoning="multi-stage work",
                ),
            )

    return PlanExecutive()


def _revision_executive_agent() -> Any:
    class RevisionExecutive:
        async def analyze(self, state):
            return ExecutiveAgentResult(
                understanding=AgentUnderstanding(
                    goal=state.get("user_input", ""),
                    summary="revision",
                    next_action="execute",
                    required_capabilities=["document_revision"],
                ),
                decision=AgentDecision(
                    action=DecisionType.EXECUTE,
                    reasoning="revision request",
                ),
            )

    return RevisionExecutive()


@pytest.mark.asyncio
async def test_progress_update_edits_single_message(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    runtime = StreamableFakeRuntime(
        final_state={
            "execution_id": "exec-progress",
            "status": "completed",
            "telegram_progress": {
                "execution_id": "exec-progress",
                "progress_percent": 100,
                "lines": [
                    {"title": "Исследование", "status_icon": "✅", "status_label": "выполнено"},
                    {"title": "Стратегия", "status_icon": "✅", "status_label": "выполнено"},
                ],
            },
            "quality_check": {"passed": True, "score": 0.9},
            "result": {"message": "Готово по стратегии."},
        },
        stream_events=[
            {
                "orchestration": {
                    "telegram_progress": {
                        "progress_percent": 50,
                        "lines": [
                            {"title": "Исследование", "status_icon": "✅", "status_label": "выполнено"},
                            {"title": "Стратегия", "status_icon": "⏳", "status_label": "выполняется"},
                        ],
                    }
                }
            }
        ],
    )
    flow = build_flow(
        runtime,
        session_manager,
        sender,
        conversation_store,
        continuation=FakeContinuation(),
        executive_agent=_plan_executive_agent(),
    )
    request = TelegramMapper().map_update(SAMPLE_UPDATE)
    assert request is not None

    await flow.handle_message(request)

    assert len(sender.sent) >= 1
    assert sender.sent[0]["text"] == "Думаю…"
    assert len(sender.edited) >= 1
    assert "Стратегия" in sender.edited[-1]["text"] or "Думаю" in sender.edited[-1]["text"]
    assert sender.deleted
    assert "Quality score" not in (sender.sent[-1]["text"] if sender.sent else "")


@pytest.mark.asyncio
async def test_approval_buttons_and_resume(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    waiting_runtime = StreamableFakeRuntime(
        final_state={
            "execution_id": "exec-approval",
            "status": "waiting_approval",
            "task_plan": {
                "goal": "test",
                "steps": [
                    {"description": "Исследование рынка", "capability": "research"},
                    {"description": "Создание стратегии", "capability": "strategy"},
                ],
            },
        }
    )
    completed_runtime = StreamableFakeRuntime(
        final_state={
            "execution_id": "exec-approved",
            "status": "completed",
            "result": {"message": "План выполнен."},
            "quality_check": {"passed": True, "score": 0.91},
        }
    )

    class SwitchingRuntime:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []
            self._first = True

        async def stream(self, user_input: str, *, trace_id=None, context=None, metadata=None):
            self.calls.append({"metadata": metadata})
            state = waiting_runtime._final_state if self._first else completed_runtime._final_state
            self._first = False
            yield {"executor": state}

        async def execute(self, *args, **kwargs):
            raise AssertionError("execute should not be called when stream is available")

    switching_runtime = SwitchingRuntime()
    flow = build_flow(
        switching_runtime,  # type: ignore[arg-type]
        session_manager,
        sender,
        conversation_store,
        continuation=FakeContinuation(),
        executive_agent=_plan_executive_agent(),
    )
    request = TelegramMapper().map_update(SAMPLE_UPDATE)
    assert request is not None
    first = await flow.handle_message(request)
    assert first["status"] == "waiting_approval"
    assert "Исследование рынка" in sender.sent[-1]["text"]
    assert sender.sent[-1]["reply_markup"]["inline_keyboard"][0][0]["text"] == "Начать"
    assert sender.deleted  # progress cleared before approval

    callback = TelegramMapper().map_callback(SAMPLE_CALLBACK_APPROVE)
    assert callback is not None
    resumed = await flow.handle_callback(callback)
    assert resumed["status"] == "completed"
    assert len(switching_runtime.calls) == 2
    assert switching_runtime.calls[1]["metadata"].get("auto_approve") is True


@pytest.mark.asyncio
async def test_approval_cancel(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    runtime = StreamableFakeRuntime(
        final_state={
            "execution_id": "exec-cancel",
            "status": "waiting_approval",
            "task_plan": {"steps": [{"description": "Шаг 1", "capability": "x"}]},
        }
    )
    orchestrator = Orchestrator(store=ExecutionStore())
    flow = build_flow(runtime, session_manager, sender, conversation_store, orchestrator=orchestrator)
    request = TelegramMapper().map_update(SAMPLE_UPDATE)
    assert request is not None
    await flow.handle_message(request)

    cancel_update = {
        "update_id": 2002,
        "callback_query": {
            "id": "cb-cancel",
            "from": {"id": 777, "is_bot": False, "first_name": "Ada"},
            "message": {
                "message_id": 50,
                "chat": {"id": 555, "type": "private"},
                "date": 1710000001,
                "text": "plan",
            },
            "data": "tg:cancel",
        },
    }
    callback = TelegramMapper().map_callback(cancel_update)
    assert callback is not None
    result = await flow.handle_callback(callback)
    assert result["status"] == "cancelled"
    assert "отменено" in result["reply"].lower()


@pytest.mark.asyncio
async def test_revision_button_prompts_for_feedback(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    flow = build_flow(
        StreamableFakeRuntime(final_state={"status": "completed", "quality_check": {"score": 0.9}}),
        session_manager,
        sender,
        conversation_store,
        continuation=FakeContinuation(),
    )
    convo = await conversation_store.get_or_create(777, 555)
    convo.flow_mode = TelegramFlowMode.COMPLETED
    convo.last_agent_state = {"status": "completed", "render_result": {"artifact_id": str(uuid4())}}
    await conversation_store.save(convo)

    callback = TelegramCallbackRequest(
        action="revise",
        telegram_user_id=777,
        telegram_chat_id=555,
        callback_query_id="cb-revise",
        callback_data="tg:revise",
    )
    result = await flow.handle_callback(callback)
    assert result["status"] == "revision_prompted"
    assert format_revision_prompt() in result["reply"]
    assert (await conversation_store.get(777)).flow_mode == TelegramFlowMode.REVISION_PROMPTED


@pytest.mark.asyncio
async def test_revision_from_text_message(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    flow = build_flow(
        StreamableFakeRuntime(final_state={"status": "completed"}),
        session_manager,
        sender,
        conversation_store,
        continuation=FakeContinuation(),
    )
    convo = await conversation_store.get_or_create(777, 555)
    convo.flow_mode = TelegramFlowMode.REVISION_PROMPTED
    convo.last_agent_state = {
        "status": "completed",
        "render_result": {"artifact_id": str(uuid4())},
        "document_ast": {"node_count": 3},
        "quality_check": {"passed": True, "score": 0.9},
    }
    await conversation_store.save(convo)

    request = TelegramExecutionRequest(
        user_input="Сделай короче и добавь больше таблиц",
        telegram_user_id=777,
        telegram_chat_id=555,
        telegram_message_id=99,
    )
    result = await flow.handle_message(request)
    assert result["status"] == "revised"
    assert "Готово" in result["reply"]


@pytest.mark.asyncio
async def test_contextual_revision_without_button(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    assert is_contextual_revision_message("Сделай короче") is True
    flow = build_flow(
        StreamableFakeRuntime(final_state={"status": "completed"}),
        session_manager,
        sender,
        conversation_store,
        continuation=FakeContinuation(),
        executive_agent=_revision_executive_agent(),
    )
    convo = await conversation_store.get_or_create(777, 555)
    convo.flow_mode = TelegramFlowMode.COMPLETED
    convo.last_agent_state = {
        "status": "completed",
        "render_result": {"artifact_id": str(uuid4())},
        "quality_check": {"passed": True, "score": 0.88},
    }
    await conversation_store.save(convo)

    request = TelegramExecutionRequest(
        user_input="Измени стиль",
        telegram_user_id=777,
        telegram_chat_id=555,
    )
    result = await flow.handle_message(request)
    assert result["status"] == "revised"


@pytest.mark.asyncio
async def test_artifact_delivery(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    artifact_id = str(uuid4())
    runtime = StreamableFakeRuntime(
        final_state={
            "execution_id": "exec-artifact",
            "status": "completed",
            "render_result": {"artifact_id": artifact_id},
            "quality_check": {"passed": True, "score": 0.92},
        }
    )
    flow = build_flow(runtime, session_manager, sender, conversation_store, continuation=FakeContinuation())
    request = TelegramMapper().map_update(SAMPLE_UPDATE)
    assert request is not None
    result = await flow.handle_message(request)
    assert result["status"] == "completed"
    assert len(sender.documents) == 1
    assert sender.documents[0]["filename"] == "КП.docx"
    assert sender.documents[0]["caption"] == "Готово."
    assert "Quality score" not in "".join(item["text"] for item in sender.sent)
    # No separate delivery summary after the file.
    assert not any("Создано:" in item["text"] for item in sender.sent)


@pytest.mark.asyncio
async def test_error_handling_without_traceback(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    class FailingRuntime:
        async def stream(self, *args, **kwargs):
            if False:
                yield {}
            raise GraphExecutionError("internal traceback details")

        async def execute(self, *args, **kwargs):
            raise GraphExecutionError("internal traceback details")

    flow = build_flow(FailingRuntime(), session_manager, sender, conversation_store)  # type: ignore[arg-type]
    request = TelegramMapper().map_update(SAMPLE_UPDATE)
    assert request is not None
    result = await flow.handle_message(request)
    assert result["status"] == "failed"
    error_text = sender.edited[-1]["text"] if sender.edited else sender.sent[-1]["text"]
    assert "traceback" not in error_text.lower()
    assert "trace_id" not in error_text.lower()
    assert "Попробовать снова" in str(
        (sender.edited[-1] if sender.edited else sender.sent[-1]).get("reply_markup")
    )


@pytest.mark.asyncio
async def test_session_persistence(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    runtime = StreamableFakeRuntime(
        final_state={
            "execution_id": "exec-session",
            "status": "completed",
            "result": {"message": "Сессия сохранена."},
            "quality_check": {"score": 0.9},
        }
    )
    flow = build_flow(runtime, session_manager, sender, conversation_store, continuation=FakeContinuation())
    request = TelegramMapper().map_update(SAMPLE_UPDATE)
    assert request is not None
    await flow.handle_message(request)
    again = await flow.handle_message(request)
    convo = await conversation_store.get(777)
    assert convo is not None
    assert convo.workspace_id is not None
    assert convo.session_id is not None
    assert "execution_id" not in (again.get("reply") or "")
    assert "uuid" not in (again.get("reply") or "").lower()


def test_approval_message_format() -> None:
    text = format_approval_message(
        {
            "steps": [
                {"description": "Исследование рынка"},
                {"description": "Создание стратегии"},
                {"description": "Подготовка презентации"},
            ]
        }
    )
    assert "Исследование рынка" in text
    assert "Начать выполнение" in text


@pytest.mark.asyncio
async def test_adapter_end_to_end_with_product_flow(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    runtime = StreamableFakeRuntime(
        final_state={
            "execution_id": "exec-e2e",
            "status": "completed",
            "result": {"message": "Готово"},
            "quality_check": {"passed": True, "score": 0.9},
        }
    )
    flow = build_flow(runtime, session_manager, sender, conversation_store, continuation=FakeContinuation())
    handler = TelegramMessageHandler(
        runtime=runtime,  # type: ignore[arg-type]
        session_manager=session_manager,
        sender=sender,
        product_flow=flow,
    )
    adapter = TelegramAdapter(
        runtime=runtime,  # type: ignore[arg-type]
        session_manager=session_manager,
        sender=sender,
        product_flow=flow,
        conversation_store=conversation_store,
    )
    result = await adapter.handle_update(SAMPLE_UPDATE)
    assert result is not None
    assert result["status"] == "completed"
