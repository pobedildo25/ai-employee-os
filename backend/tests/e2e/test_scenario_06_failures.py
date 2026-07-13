from uuid import uuid4

import pytest

from app.agent_runtime.exceptions import GraphExecutionError
from app.adapters.telegram.conversation_store import TelegramConversationStore
from app.adapters.telegram.flow import TelegramProductFlow
from app.adapters.telegram.mapper import TelegramMapper
from app.adapters.telegram.sender import InMemoryTelegramSender
from app.adapters.telegram.session import TelegramSessionManager
from app.document_intelligence.pipeline import DocumentPipeline
from app.file_processing.processor import FileProcessor
from app.orchestration.execution_graph import build_execution_graph
from app.orchestration.models import ExecutionRecord
from app.orchestration.orchestrator import Orchestrator
from app.orchestration.state_manager import StateManager
from app.orchestration.store import ExecutionStore
from app.planning.parsers.plan_parser import parse_task_plan
from app.skills.registry import create_capability_registry
from app.workspace.manager import WorkspaceManager
from app.workspace.repositories.workspace_repository import InMemoryWorkspaceRepository
from app.workspace.service import WorkspaceService
from tests.llm_fixtures import plan_json
from tests.test_telegram_adapter import SAMPLE_UPDATE
from tests.test_telegram_product_ux import StreamableFakeRuntime


@pytest.mark.asyncio
async def test_llm_timeout_retries_then_friendly_error() -> None:
    from app.agents.decision.models import AgentDecision, DecisionType
    from app.agents.executive.models import AgentUnderstanding, ExecutiveAgentResult

    class TaskExecutive:
        async def analyze(self, state):
            return ExecutiveAgentResult(
                understanding=AgentUnderstanding(
                    goal=state.get("user_input", ""),
                    summary="task",
                    next_action="execute",
                ),
                decision=AgentDecision(action=DecisionType.EXECUTE, reasoning="task"),
            )

    sender = InMemoryTelegramSender()
    flow = TelegramProductFlow(
        runtime=StreamableFakeRuntime(final_state={"status": "completed"}),  # type: ignore[arg-type]
        session_manager=TelegramSessionManager(WorkspaceService(WorkspaceManager(InMemoryWorkspaceRepository()))),
        sender=sender,
        conversation_store=TelegramConversationStore(),
        executive_agent=TaskExecutive(),  # type: ignore[arg-type]
    )

    class FailingRuntime:
        async def stream(self, *args, **kwargs):
            if False:
                yield {}
            raise GraphExecutionError("internal timeout details")

        async def execute(self, *args, **kwargs):
            raise GraphExecutionError("internal timeout details")

    flow._runtime = FailingRuntime()  # type: ignore[assignment]
    request = TelegramMapper().map_update(SAMPLE_UPDATE)
    result = await flow.handle_message(request)
    assert result["status"] == "failed"
    error_payload = sender.edited[-1] if sender.edited else sender.sent[-1]
    assert "traceback" not in error_payload["text"].lower()
    assert "Попробовать снова" in str(error_payload.get("reply_markup"))


@pytest.mark.asyncio
async def test_unknown_capability_fails_gracefully(settings) -> None:
    registry = create_capability_registry(settings)
    orchestrator = Orchestrator(store=ExecutionStore())
    plan = parse_task_plan(
        plan_json(
            steps=[{"description": "Unknown", "capability": "nonexistent_capability", "dependencies": []}],
        )
    )
    graph = build_execution_graph(plan)
    state = StateManager().create_state("fail-1", graph)
    final_state, execution = await orchestrator.execute(
        graph,
        plan,
        registry,
        state,
        trace_id="fail-trace",
    )
    assert execution.status.value == "FAILED"
    assert final_state.failed_nodes


@pytest.mark.asyncio
async def test_broken_artifact_validation(settings, tmp_path) -> None:
    pipeline = DocumentPipeline(processor=FileProcessor())
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"not-a-real-pdf")
    with pytest.raises((Exception, ValueError)):
        pipeline.process_bytes(
            artifact_id=uuid4(),
            title="Broken",
            data=broken.read_bytes(),
            filename="broken.pdf",
            mime_type="application/pdf",
        )


@pytest.mark.asyncio
async def test_cancelled_execution_status() -> None:
    orchestrator = Orchestrator(store=ExecutionStore())
    plan = parse_task_plan(plan_json())
    graph = build_execution_graph(plan)
    state = StateManager().create_state("cancel-1", graph)
    orchestrator._store.save(
        ExecutionRecord(
            execution_id="cancel-1",
            graph=graph,
            state=state,
            task_plan=plan.model_dump(mode="json"),
        )
    )
    cancelled = orchestrator.cancel_execution("cancel-1")
    assert cancelled is not None
    assert cancelled.control_status.value == "CANCELLED"
