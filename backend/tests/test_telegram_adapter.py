from typing import Any
from uuid import UUID

import pytest

from app.adapters.telegram.bot import TelegramAdapter, TelegramBot
from app.adapters.telegram.dispatcher import TelegramDispatcher
from app.adapters.telegram.handlers import TelegramMessageHandler
from app.adapters.telegram.mapper import TelegramMapper
from app.adapters.telegram.models import TelegramUpdate
from app.adapters.telegram.sender import InMemoryTelegramSender
from app.adapters.telegram.session import TelegramSessionManager, telegram_client_id
from app.workspace.manager import WorkspaceManager
from app.workspace.repositories.workspace_repository import InMemoryWorkspaceRepository
from app.workspace.service import WorkspaceService


SAMPLE_UPDATE = {
    "update_id": 1001,
    "message": {
        "message_id": 42,
        "date": 1710000000,
        "text": "Подготовь КП для клиента",
        "chat": {"id": 555, "type": "private"},
        "from": {
            "id": 777,
            "is_bot": False,
            "first_name": "Ada",
            "username": "ada",
        },
    },
}


class FakeAgentRuntime:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def execute(
        self,
        user_input: str,
        *,
        trace_id: str | None = None,
        context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "user_input": user_input,
                "trace_id": trace_id,
                "context": context or {},
                "metadata": metadata or {},
            }
        )
        return {
            "execution_id": "exec-tg-1",
            "trace_id": trace_id or "trace-tg-1",
            "status": "completed",
            "result": {"message": f"Ответ на: {user_input}"},
            "decision": {"action": "respond", "response_message": f"Ответ на: {user_input}"},
            "quality_check": {"passed": True, "score": 0.9},
        }

    async def stream(
        self,
        user_input: str,
        *,
        trace_id: str | None = None,
        context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        state = await self.execute(
            user_input,
            trace_id=trace_id,
            context=context,
            metadata=metadata,
        )
        yield {"executor": state}


class TaskExecutiveAgent:
    """Routes Telegram adapter tests into the execution path without OpenRouter."""

    async def analyze(self, state):
        from app.agents.decision.models import AgentDecision, DecisionType
        from app.agents.executive.models import AgentUnderstanding, ExecutiveAgentResult

        return ExecutiveAgentResult(
            understanding=AgentUnderstanding(
                goal=state.get("user_input", ""),
                summary="task",
                next_action="execute",
            ),
            decision=AgentDecision(action=DecisionType.EXECUTE, reasoning="adapter test"),
        )


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
def runtime() -> FakeAgentRuntime:
    return FakeAgentRuntime()


def test_telegram_mapper() -> None:
    mapper = TelegramMapper()
    request = mapper.map_update(SAMPLE_UPDATE)
    assert request is not None
    assert request.user_input == "Подготовь КП для клиента"
    assert request.telegram_user_id == 777
    assert request.telegram_chat_id == 555
    assert request.metadata["source"] == "telegram"

    empty = mapper.map_update({"update_id": 1, "message": {"message_id": 1, "chat": {"id": 1, "type": "private"}}})
    assert empty is None


def test_extract_reply_text() -> None:
    text = TelegramMapper.extract_reply_text(
        {"result": {"message": "hello"}, "decision": {"response_message": "other"}}
    )
    assert text == "hello"


@pytest.mark.asyncio
async def test_telegram_session_manager(session_manager: TelegramSessionManager) -> None:
    snapshot = await session_manager.resolve(777)
    assert snapshot["client_id"] == str(telegram_client_id(777))
    assert snapshot["active_session_id"] is not None
    assert session_manager.get_bound_workspace_id(777) == UUID(snapshot["workspace_id"])

    again = await session_manager.resolve(777)
    assert again["workspace_id"] == snapshot["workspace_id"]


@pytest.mark.asyncio
async def test_telegram_session_ensures_default_project(
    workspace_service: WorkspaceService,
) -> None:
    from dataclasses import dataclass, field
    from datetime import datetime, timezone

    from app.schemas.project import ProjectCreate, ProjectUpdate

    @dataclass
    class _Project:
        id: UUID
        client_id: UUID
        name: str
        description: str | None = None
        status: str = "active"
        created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
        updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    class FakeProjectRepository:
        def __init__(self) -> None:
            self.items: list[_Project] = []

        async def create(self, data: ProjectCreate) -> _Project:
            project = _Project(
                id=UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
                client_id=data.client_id,
                name=data.name,
                description=data.description,
                status=data.status,
            )
            self.items.append(project)
            return project

        async def get_by_id(self, project_id: UUID) -> _Project | None:
            return next((p for p in self.items if p.id == project_id), None)

        async def list_by_client(
            self, client_id: UUID, skip: int = 0, limit: int = 100
        ) -> list[_Project]:
            matched = [p for p in self.items if p.client_id == client_id]
            return matched[skip : skip + limit]

        async def list_all(self, skip: int = 0, limit: int = 100) -> list[_Project]:
            return self.items[skip : skip + limit]

        async def update(self, project_id: UUID, data: ProjectUpdate) -> _Project | None:
            return await self.get_by_id(project_id)

        async def delete(self, project_id: UUID) -> bool:
            return False

    projects = FakeProjectRepository()
    manager = TelegramSessionManager(
        workspace_service=workspace_service,
        project_repository=projects,  # type: ignore[arg-type]
        bindings={},
    )
    snapshot = await manager.resolve(888)
    assert snapshot["active_project_id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert len(projects.items) == 1

    again = await manager.resolve(888)
    assert again["active_project_id"] == snapshot["active_project_id"]
    assert len(projects.items) == 1


@pytest.mark.asyncio
async def test_telegram_handler(
    runtime: FakeAgentRuntime,
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
) -> None:
    mapper = TelegramMapper()
    handler = TelegramMessageHandler(
        runtime=runtime,  # type: ignore[arg-type]
        session_manager=session_manager,
        sender=sender,
        mapper=mapper,
    )
    request = mapper.map_update(SAMPLE_UPDATE)
    assert request is not None
    result = await handler.handle(request)

    assert result["status"] == "completed"
    assert result["reply"].startswith("Готово") or result["reply"].startswith("Ответ на:")
    assert len(runtime.calls) == 1
    assert runtime.calls[0]["user_input"] == "Подготовь КП для клиента"
    assert "workspace_id" in runtime.calls[0]["metadata"]
    assert len(sender.sent) == 1
    assert sender.sent[0]["chat_id"] == 555
    assert sender.sent[0]["text"] == "Ответ на: Подготовь КП для клиента"


@pytest.mark.asyncio
async def test_telegram_adapter(
    runtime: FakeAgentRuntime,
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
) -> None:
    adapter = TelegramAdapter(
        runtime=runtime,  # type: ignore[arg-type]
        session_manager=session_manager,
        sender=sender,
        enabled=True,
        executive_agent=TaskExecutiveAgent(),  # type: ignore[arg-type]
    )
    result = await adapter.handle_update(SAMPLE_UPDATE)
    assert result is not None
    assert result["execution_id"] == "exec-tg-1"
    # Single-step EXECUTE: no progress theater; final reply only.
    assert all(item["text"] != "Думаю…" for item in sender.sent)
    assert any(item["text"].startswith("Ответ на:") for item in sender.sent)

    disabled = TelegramAdapter(
        runtime=runtime,  # type: ignore[arg-type]
        session_manager=session_manager,
        sender=sender,
        enabled=False,
        executive_agent=TaskExecutiveAgent(),  # type: ignore[arg-type]
    )
    assert await disabled.handle_update(SAMPLE_UPDATE) is None


@pytest.mark.asyncio
async def test_dispatcher_and_bot(
    runtime: FakeAgentRuntime,
    session_manager: TelegramSessionManager,
    sender: InMemoryTelegramSender,
) -> None:
    adapter = TelegramAdapter(
        runtime=runtime,  # type: ignore[arg-type]
        session_manager=session_manager,
        sender=sender,
        executive_agent=TaskExecutiveAgent(),  # type: ignore[arg-type]
    )
    bot = TelegramBot(adapter, token="test-token")
    result = await bot.process_update(SAMPLE_UPDATE)
    assert result is not None
    reply = result.get("reply") or ""
    assert reply.startswith("Готово") or reply.startswith("Ответ на:")

    dispatcher = TelegramDispatcher(adapter.handler)
    skipped = await dispatcher.dispatch({"update_id": 2})
    assert skipped is None
