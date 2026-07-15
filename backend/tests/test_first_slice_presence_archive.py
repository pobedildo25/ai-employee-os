import pytest

from app.adapters.telegram.conversation_store import TelegramConversationStore
from app.adapters.telegram.factory import create_telegram_adapter
from app.adapters.telegram.flow import TelegramProductFlow
from app.adapters.telegram.mapper import TelegramMapper
from app.adapters.telegram.progress import TelegramProgressMessenger
from app.adapters.telegram.sender import InMemoryTelegramSender
from app.adapters.telegram.session import TelegramSessionManager
from app.agents.decision.models import AgentDecision, DecisionType
from app.agents.executive.models import AgentUnderstanding, ExecutiveAgentResult
from app.core.config import Settings
from app.llm.gateway import LLMGateway
from app.llm.models import LLMMessage, LLMRequest, LLMResponse, TokenUsage
from app.research.providers.openrouter_online_provider import _parse_search_payload
from app.ux.status_copy import STATUS_LOOKING, UNSUPPORTED_PHOTO
from app.workspace.manager import WorkspaceManager
from app.workspace.repositories.workspace_repository import InMemoryWorkspaceRepository
from app.workspace.service import WorkspaceService


class ChatExecutive:
    async def analyze(self, state) -> ExecutiveAgentResult:
        return ExecutiveAgentResult(
            understanding=AgentUnderstanding(
                goal=state.get("user_input", ""),
                summary="classified",
                next_action="respond",
            ),
            decision=AgentDecision(
                action=DecisionType.RESPOND,
                reasoning="chat",
                response_message="Привет! Краткий ответ.",
            ),
        )


class FakeRuntime:
    async def stream(self, *args, **kwargs):
        if False:
            yield {}
        return

    async def run(self, *args, **kwargs):
        return {"status": "completed"}


class RecordingProvider:
    def __init__(self) -> None:
        self.requests: list[LLMRequest] = []

    async def chat(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(
            content="{}",
            model=request.model or "test",
            usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            latency_ms=1.0,
        )


@pytest.mark.asyncio
async def test_chat_edits_single_status_message() -> None:
    sender = InMemoryTelegramSender()
    store = TelegramConversationStore()
    workspace = WorkspaceService(WorkspaceManager(InMemoryWorkspaceRepository()))
    sessions = TelegramSessionManager(workspace_service=workspace)
    flow = TelegramProductFlow(
        runtime=FakeRuntime(),
        session_manager=sessions,
        sender=sender,
        conversation_store=store,
        progress_messenger=TelegramProgressMessenger(sender, min_interval_seconds=0.0),
        executive_agent=ChatExecutive(),
    )
    update = {
        "update_id": 1,
        "message": {
            "message_id": 10,
            "text": "привет",
            "chat": {"id": 77, "type": "private"},
            "from": {"id": 77, "is_bot": False, "first_name": "T"},
        },
    }
    request = TelegramMapper().map_update(update)
    assert request is not None
    result = await flow.handle_message(request)
    assert result["status"] == "completed"
    assert sender.sent[0]["text"] == STATUS_LOOKING
    assert sender.edited
    # Greetings are answered locally so basic chat survives LLM outages.
    assert "NOVA" in sender.edited[-1]["text"]


@pytest.mark.asyncio
async def test_photo_gets_honest_decline() -> None:
    sender = InMemoryTelegramSender()
    settings = Settings(
        telegram_enabled=True,
        telegram_bot_token="",
        openrouter_api_key="change-me",
    )
    workspace = WorkspaceService(WorkspaceManager(InMemoryWorkspaceRepository()))
    adapter = create_telegram_adapter(
        runtime=FakeRuntime(),
        workspace_service=workspace,
        settings=settings,
        sender=sender,
        executive_agent=ChatExecutive(),
    )
    result = await adapter.handle_update(
        {
            "update_id": 2,
            "message": {
                "message_id": 11,
                "chat": {"id": 88, "type": "private"},
                "from": {"id": 88, "is_bot": False, "first_name": "T"},
                "photo": [{"file_id": "abc", "width": 100, "height": 100}],
            },
        }
    )
    assert result is not None
    assert result["status"] == "unsupported_media"
    assert sender.sent[-1]["text"] == UNSUPPORTED_PHOTO


@pytest.mark.asyncio
async def test_llm_gateway_applies_max_tokens_cap() -> None:
    settings = Settings(
        default_llm_model="openai/gpt-4o-mini",
        heavy_llm_model="anthropic/claude-sonnet-4",
        llm_max_tokens=1000,
        llm_heavy_max_tokens=2000,
        fallback_llm_model="",
        secondary_fallback_llm_model="",
    )
    provider = RecordingProvider()
    gateway = LLMGateway(provider, settings)
    await gateway.complete(
        [LLMMessage(role="user", content="hi")],
        max_tokens=64000,
    )
    assert provider.requests[0].max_tokens == 1000
    await gateway.complete(
        [LLMMessage(role="user", content="doc")],
        metadata={"use_heavy_model": True},
    )
    assert provider.requests[1].max_tokens == 2000
    assert provider.requests[1].model == "anthropic/claude-sonnet-4"


def test_openrouter_online_parser_reads_json_array() -> None:
    payload = _parse_search_payload(
        '[{"title":"A","url":"https://example.com","snippet":"hello"}]',
        limit=5,
    )
    assert len(payload) == 1
    assert payload[0]["title"] == "A"


@pytest.mark.asyncio
async def test_greeting_uses_local_reply_without_llm() -> None:
    class ExplodingExecutive:
        async def analyze(self, state):
            raise AssertionError("LLM must not be called for local greeting")

    sender = InMemoryTelegramSender()
    store = TelegramConversationStore()
    workspace = WorkspaceService(WorkspaceManager(InMemoryWorkspaceRepository()))
    sessions = TelegramSessionManager(workspace_service=workspace)
    flow = TelegramProductFlow(
        runtime=FakeRuntime(),
        session_manager=sessions,
        sender=sender,
        conversation_store=store,
        progress_messenger=TelegramProgressMessenger(sender, min_interval_seconds=0.0),
        executive_agent=ExplodingExecutive(),
    )
    request = TelegramMapper().map_update(
        {
            "update_id": 3,
            "message": {
                "message_id": 12,
                "text": "привет",
                "chat": {"id": 99, "type": "private"},
                "from": {"id": 99, "is_bot": False, "first_name": "T"},
            },
        }
    )
    assert request is not None
    result = await flow.handle_message(request)
    assert result["status"] == "completed"
    assert sender.sent[0]["text"] == STATUS_LOOKING
    assert "NOVA" in sender.edited[-1]["text"]


@pytest.mark.asyncio
async def test_llm_failure_replaces_looking_status() -> None:
    from app.llm.exceptions import LLMProviderError
    from app.ux.status_copy import LLM_UNAVAILABLE

    class ExplodingExecutive:
        async def analyze(self, state):
            raise LLMProviderError("OpenRouter error 402: Insufficient credits")

    sender = InMemoryTelegramSender()
    store = TelegramConversationStore()
    workspace = WorkspaceService(WorkspaceManager(InMemoryWorkspaceRepository()))
    sessions = TelegramSessionManager(workspace_service=workspace)
    flow = TelegramProductFlow(
        runtime=FakeRuntime(),
        session_manager=sessions,
        sender=sender,
        conversation_store=store,
        progress_messenger=TelegramProgressMessenger(sender, min_interval_seconds=0.0),
        executive_agent=ExplodingExecutive(),
    )
    request = TelegramMapper().map_update(
        {
            "update_id": 4,
            "message": {
                "message_id": 13,
                "text": "что такое brand book",
                "chat": {"id": 99, "type": "private"},
                "from": {"id": 99, "is_bot": False, "first_name": "T"},
            },
        }
    )
    assert request is not None
    result = await flow.handle_message(request)
    assert result["status"] == "failed"
    assert sender.sent[0]["text"] == STATUS_LOOKING
    assert sender.edited[-1]["text"] == LLM_UNAVAILABLE


@pytest.mark.asyncio
async def test_fx_local_reply_edits_status(monkeypatch) -> None:
    async def fake_fx(_text: str):
        return "Курс доллара ЦБ РФ на 2026-07-15: 90.0000 ₽."

    monkeypatch.setattr(
        "app.adapters.telegram.flow.maybe_local_reply",
        fake_fx,
    )
    sender = InMemoryTelegramSender()
    store = TelegramConversationStore()
    workspace = WorkspaceService(WorkspaceManager(InMemoryWorkspaceRepository()))
    sessions = TelegramSessionManager(workspace_service=workspace)
    flow = TelegramProductFlow(
        runtime=FakeRuntime(),
        session_manager=sessions,
        sender=sender,
        conversation_store=store,
        progress_messenger=TelegramProgressMessenger(sender, min_interval_seconds=0.0),
        executive_agent=ChatExecutive(),
    )
    request = TelegramMapper().map_update(
        {
            "update_id": 5,
            "message": {
                "message_id": 14,
                "text": "курс доллара",
                "chat": {"id": 88, "type": "private"},
                "from": {"id": 88, "is_bot": False, "first_name": "T"},
            },
        }
    )
    assert request is not None
    result = await flow.handle_message(request)
    assert result["status"] == "completed"
    assert "90.0000" in sender.edited[-1]["text"]
