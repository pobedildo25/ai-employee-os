"""Stage F — Product behaviour UX fixes vs modern AI assistants."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.adapters.telegram.conversation_store import TelegramConversationStore, TelegramFlowMode
from app.adapters.telegram.models import TelegramExecutionRequest
from app.adapters.telegram.presenter import format_delivery_caption, _plural_files
from app.adapters.telegram.sender import InMemoryTelegramSender
from app.adapters.telegram.session import TelegramSessionManager
from app.agent_runtime.state.models import create_initial_state
from app.agents.decision.models import AgentDecision, DecisionType
from app.agents.executive.models import AgentUnderstanding, ExecutiveAgentResult
from app.agents.executive.node import ChatResponseNode, ExecutiveAgentNode
from app.planning.direct_plan import build_direct_execution_plan
from app.planning.policies.execution_policy import requires_approval
from app.workspace.manager import WorkspaceManager
from app.workspace.repositories.workspace_repository import InMemoryWorkspaceRepository
from app.workspace.service import WorkspaceService
from tests.test_telegram_product_ux import FakeContinuation, StreamableFakeRuntime, build_flow


def test_plural_files_russian() -> None:
    assert _plural_files(1) == "файл"
    assert _plural_files(2) == "файла"
    assert _plural_files(5) == "файлов"
    assert format_delivery_caption([{}, {}, {}, {}, {}]) == "Готово · 5 файлов"


def test_direct_plan_uses_russian_step_labels() -> None:
    plan = build_direct_execution_plan(
        goal="КП",
        summary="draft",
        required_capabilities=["document_generation"],
    )
    assert "Execute capability" not in plan.steps[0].description
    assert plan.steps[0].description == "Подготовка документа"


def test_single_step_create_plan_skips_approval() -> None:
    plan = build_direct_execution_plan(
        goal="x", summary="x", required_capabilities=["strategy_analysis"]
    )
    assert requires_approval("CREATE_PLAN", plan) is False


@pytest.mark.asyncio
async def test_chat_response_fallback_is_not_greeting() -> None:
    node = ChatResponseNode()
    state = create_initial_state(execution_id="e1", trace_id="t1", user_input="вопрос")
    state["decision"] = {"action": "RESPOND", "reasoning": "x"}
    update = node(state)
    assert "Привет" not in update["result"]["message"]


@pytest.mark.asyncio
async def test_executive_node_reuses_preclassification() -> None:
    class CountingAgent:
        def __init__(self) -> None:
            self.calls = 0

        async def analyze(self, state):
            self.calls += 1
            raise AssertionError("should not call LLM")

    agent = CountingAgent()
    node = ExecutiveAgentNode(agent)  # type: ignore[arg-type]
    state = create_initial_state(execution_id="e1", trace_id="t1", user_input="Сделай КП")
    state["metadata"] = {
        "skip_executive_llm": True,
        "preclassified_decision": {
            "action": "EXECUTE",
            "reasoning": "draft",
        },
        "preclassified_understanding": {
            "goal": "КП",
            "summary": "draft",
            "next_action": "execute",
        },
    }
    update = await node(state)
    assert agent.calls == 0
    assert update["decision"]["action"] == "EXECUTE"
    assert update["metadata"]["executive_reused_classification"] is True


@pytest.mark.asyncio
async def test_missing_executive_does_not_start_task_pipeline() -> None:
    runtime = StreamableFakeRuntime(final_state={"status": "completed"})
    sender = InMemoryTelegramSender()
    store = TelegramConversationStore()
    sessions = TelegramSessionManager(
        workspace_service=WorkspaceService(WorkspaceManager(InMemoryWorkspaceRepository())),
        bindings={},
    )
    flow = build_flow(runtime, sessions, sender, store)
    flow._executive_agent = None

    result = await flow.handle_message(
        TelegramExecutionRequest(
            user_input="Привет",
            telegram_user_id=1,
            telegram_chat_id=1,
        )
    )
    assert result["intent"] == "degraded"
    assert runtime.calls == []
    assert "Думаю" not in (result.get("reply") or "")


@pytest.mark.asyncio
async def test_new_task_after_completed_is_not_forced_into_revision() -> None:
    class SwitchingExecutive:
        async def analyze(self, state):
            return ExecutiveAgentResult(
                understanding=AgentUnderstanding(
                    goal=state.get("user_input", ""),
                    summary="new task",
                    next_action="execute",
                    required_capabilities=["strategy_analysis"],
                ),
                decision=AgentDecision(
                    action=DecisionType.EXECUTE,
                    reasoning="new deliverable",
                ),
            )

    runtime = StreamableFakeRuntime(
        final_state={
            "execution_id": "exec-new",
            "status": "completed",
            "result": {"message": "Новый SWOT готов"},
            "quality_check": {"passed": True, "score": 0.9},
        }
    )
    sender = InMemoryTelegramSender()
    store = TelegramConversationStore()
    sessions = TelegramSessionManager(
        workspace_service=WorkspaceService(WorkspaceManager(InMemoryWorkspaceRepository())),
        bindings={},
    )
    flow = build_flow(runtime, sessions, sender, store, continuation=FakeContinuation())
    flow._executive_agent = SwitchingExecutive()  # type: ignore[assignment]

    convo = store.get_or_create(777, 555)
    convo.flow_mode = TelegramFlowMode.COMPLETED
    convo.last_agent_state = {
        "status": "completed",
        "render_result": {"artifact_id": str(uuid4())},
    }
    store.save(convo)

    result = await flow.handle_message(
        TelegramExecutionRequest(
            user_input="Сделай SWOT для другого клиента Aurora",
            telegram_user_id=777,
            telegram_chat_id=555,
        )
    )
    assert result["status"] == "completed"
    assert result.get("contextual") is not True
    assert runtime.calls
