import pytest

from app.adapters.telegram.bot import TelegramAdapter
from app.adapters.telegram.conversation_store import TelegramConversationStore
from app.adapters.telegram.continuation import TelegramArtifactDelivery
from app.adapters.telegram.flow import TelegramProductFlow
from app.adapters.telegram.mapper import TelegramMapper
from app.adapters.telegram.progress import TelegramProgressMessenger
from app.adapters.telegram.sender import InMemoryTelegramSender
from app.adapters.telegram.session import TelegramSessionManager
from app.orchestration.orchestrator import Orchestrator
from app.orchestration.store import ExecutionStore
from app.workspace.manager import WorkspaceManager
from app.workspace.repositories.workspace_repository import InMemoryWorkspaceRepository
from app.workspace.service import WorkspaceService
from tests.e2e.helpers import build_e2e_runtime
from tests.llm_fixtures import executive_json, plan_json, review_json
from tests.test_telegram_adapter import SAMPLE_UPDATE
from tests.test_telegram_product_ux import FakeArtifactDelivery, FakeContinuation, SAMPLE_CALLBACK_APPROVE, StreamableFakeRuntime


@pytest.mark.asyncio
async def test_telegram_full_flow_with_progress_approval_and_delivery(settings, artifact_service) -> None:
    from tests.llm_fixtures import mock_gateway

    waiting_state = {
        "execution_id": "tg-e2e-1",
        "status": "waiting_approval",
        "task_plan": {
            "goal": "Подготовь презентацию",
            "steps": [
                {"description": "Design slides", "capability": "presentation_design"},
                {"description": "Render deck", "capability": "document_rendering", "dependencies": [0]},
            ],
        },
        "telegram_progress": {
            "progress_percent": 0,
            "lines": [{"title": "Design slides", "status_icon": "⌛", "status_label": "ожидает"}],
        },
    }
    completed_state = {
        "execution_id": "tg-e2e-2",
        "status": "completed",
        "quality_check": {"passed": True, "score": 0.9},
        "render_result": {"artifact_id": "00000000-0000-0000-0000-000000000001"},
        "telegram_progress": {
            "progress_percent": 100,
            "lines": [{"title": "Render deck", "status_icon": "✅", "status_label": "выполнено"}],
        },
    }

    class TelegramE2ERuntime:
        def __init__(self) -> None:
            self.calls = 0

        async def stream(self, user_input, *, trace_id=None, context=None, metadata=None):
            self.calls += 1
            state = waiting_state if self.calls == 1 else completed_state
            yield {"executor": state}

    sender = InMemoryTelegramSender()
    workspace = WorkspaceService(WorkspaceManager(InMemoryWorkspaceRepository()))
    store = TelegramConversationStore()
    flow = TelegramProductFlow(
        runtime=TelegramE2ERuntime(),  # type: ignore[arg-type]
        session_manager=TelegramSessionManager(workspace_service=workspace),
        sender=sender,
        conversation_store=store,
        progress_messenger=TelegramProgressMessenger(sender, min_interval_seconds=0.0),
        continuation=FakeContinuation(),
        artifact_delivery=FakeArtifactDelivery(),
        orchestrator=Orchestrator(store=ExecutionStore()),
    )
    adapter = TelegramAdapter(
        runtime=TelegramE2ERuntime(),  # type: ignore[arg-type]
        session_manager=TelegramSessionManager(workspace_service=workspace),
        sender=sender,
        product_flow=flow,
        conversation_store=store,
    )

    first = await adapter.handle_update(SAMPLE_UPDATE)
    assert first is not None
    assert first["status"] == "waiting_approval"
    assert "Начать выполнение" in sender.sent[-1]["text"]
    assert sender.sent[0]["text"] == "Смотрю…"
    assert sender.edited

    approved = await adapter.handle_update(SAMPLE_CALLBACK_APPROVE)
    assert approved is not None
    assert approved["status"] == "completed"
    assert sender.documents
    assert "Готово" in sender.sent[-1]["text"]

    convo = store.get(SAMPLE_UPDATE["message"]["from"]["id"])
    assert convo is not None
    assert convo.workspace_id is not None
    assert convo.session_id is not None
