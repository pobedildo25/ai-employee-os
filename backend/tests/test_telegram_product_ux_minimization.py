"""Stage D — Telegram product UX: fewer bubbles, ChatGPT-like thin transport."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from app.adapters.telegram.conversation_store import TelegramConversationStore, TelegramFlowMode
from app.adapters.telegram.models import TelegramCallbackRequest, TelegramExecutionRequest
from app.adapters.telegram.presenter import (
    format_delivery_summary,
    format_progress_header,
    format_revision_prompt,
    format_runtime_error_message,
    format_telegram_progress,
)
from app.adapters.telegram.sender import InMemoryTelegramSender
from app.adapters.telegram.session import TelegramSessionManager
from app.agent_runtime.exceptions import GraphExecutionError
from app.workspace.manager import WorkspaceManager
from app.workspace.repositories.workspace_repository import InMemoryWorkspaceRepository
from app.workspace.service import WorkspaceService
from tests.test_telegram_adapter import SAMPLE_UPDATE
from tests.test_telegram_product_ux import (
    FakeArtifactDelivery,
    FakeContinuation,
    StreamableFakeRuntime,
    build_flow,
)


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


def test_progress_copy_is_quiet() -> None:
    assert format_progress_header() == "Думаю…"
    assert "NOVA" not in format_progress_header()
    text = format_telegram_progress(
        {
            "lines": [
                {"title": "Исследование", "status_label": "выполнено"},
                {"title": "Стратегия", "status_label": "выполняется"},
            ]
        }
    )
    assert text == "Думаю…\nСтратегия"
    assert "✅" not in text


def test_delivery_summary_has_no_quality_score() -> None:
    text = format_delivery_summary(
        [{"name": "КП.docx"}],
        {"quality_check": {"score": 0.99}},
    )
    assert text == "Готово."
    assert "Quality" not in text
    assert "Создано" not in text


def test_runtime_error_hides_internal_ids() -> None:
    text = format_runtime_error_message(
        trace_id="trace-x",
        execution_id="exec-x",
        reason="timeout",
    )
    assert "trace" not in text.lower()
    assert "exec-x" not in text
    assert "timeout" in text


def test_revision_prompt_is_one_line() -> None:
    assert format_revision_prompt() == "Что изменить?"
    assert "•" not in format_revision_prompt()


@pytest.mark.asyncio
async def test_successful_task_clears_progress_and_sends_one_reply(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    runtime = StreamableFakeRuntime(
        final_state={
            "execution_id": "exec-min",
            "status": "completed",
            "result": {"message": "Краткий ответ по стратегии."},
            "quality_check": {"passed": True, "score": 0.91},
        }
    )
    flow = build_flow(runtime, session_manager, sender, conversation_store, continuation=FakeContinuation())
    from app.adapters.telegram.mapper import TelegramMapper

    request = TelegramMapper().map_update(SAMPLE_UPDATE)
    assert request is not None
    result = await flow.handle_message(request)

    assert result["status"] == "completed"
    assert sender.sent[0]["text"] == "Думаю…"
    assert sender.deleted
    # Final user-visible text message after progress start:
    user_texts = [item["text"] for item in sender.sent if item["text"] != "Думаю…"]
    assert user_texts == ["Краткий ответ по стратегии."]
    assert all(item.get("reply_markup") is None for item in sender.sent if item["text"] != "Думаю…")


@pytest.mark.asyncio
async def test_artifact_delivery_uses_caption_not_extra_summary(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    runtime = StreamableFakeRuntime(
        final_state={
            "execution_id": "exec-file",
            "status": "completed",
            "render_result": {"artifact_id": str(uuid4())},
            "quality_check": {"score": 0.92},
        }
    )
    flow = build_flow(runtime, session_manager, sender, conversation_store, continuation=FakeContinuation())
    from app.adapters.telegram.mapper import TelegramMapper

    request = TelegramMapper().map_update(SAMPLE_UPDATE)
    assert request is not None
    await flow.handle_message(request)

    assert len(sender.documents) == 1
    assert sender.documents[0]["caption"] == "Готово."
    assert not any("Quality" in item["text"] for item in sender.sent)
    assert not any("Создано:" in item["text"] for item in sender.sent)


@pytest.mark.asyncio
async def test_error_is_single_edited_bubble(
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
    conversation_store: TelegramConversationStore,
) -> None:
    class FailingRuntime:
        async def stream(self, *args, **kwargs):
            if False:
                yield {}
            raise GraphExecutionError(
                "Workflow stream failed: boom",
                execution_id="exec-1",
                trace_id="trace-1",
            )

        async def execute(self, *args, **kwargs):
            raise GraphExecutionError("boom")

    flow = build_flow(FailingRuntime(), session_manager, sender, conversation_store)  # type: ignore[arg-type]
    from app.adapters.telegram.mapper import TelegramMapper

    request = TelegramMapper().map_update(SAMPLE_UPDATE)
    assert request is not None
    await flow.handle_message(request)

    assert len(sender.sent) == 1  # only progress start
    assert len(sender.edited) == 1  # progress replaced with error
    assert "Не удалось выполнить задачу" in sender.edited[0]["text"]
    assert "trace_id" not in sender.edited[0]["text"].lower()


@pytest.mark.asyncio
async def test_revision_button_asks_one_short_question(
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
    convo.flow_mode = TelegramFlowMode.COMPLETED
    convo.last_agent_state = {"status": "completed"}
    await conversation_store.save(convo)

    result = await flow.handle_callback(
        TelegramCallbackRequest(
            action="revise",
            telegram_user_id=777,
            telegram_chat_id=555,
            callback_query_id="cb",
            callback_data="tg:revise",
        )
    )
    assert result["reply"] == "Что изменить?"
    assert (await conversation_store.get(777)).flow_mode == TelegramFlowMode.REVISION_PROMPTED
