from uuid import uuid4

import pytest

from app.agent_runtime.state.models import create_initial_state
from app.context.builder import create_context_builder
from app.context.models import ExecutionContext
from app.context.priority import CONTEXT_PRIORITY, build_prioritized_context
from app.workspace.manager import WorkspaceManager
from app.workspace.models import Conversation, Workspace, WorkspaceSession, WorkspaceSessionStatus
from app.workspace.nodes.workspace_node import WorkspaceNode
from app.workspace.repositories.workspace_repository import InMemoryWorkspaceRepository
from app.workspace.service import WorkspaceService


@pytest.fixture
def client_id():
    return uuid4()


@pytest.fixture
def project_id():
    return uuid4()


@pytest.fixture
def manager() -> WorkspaceManager:
    return WorkspaceManager(InMemoryWorkspaceRepository())


@pytest.fixture
def service(manager: WorkspaceManager) -> WorkspaceService:
    return WorkspaceService(manager)


@pytest.mark.asyncio
async def test_workspace_model_and_open(manager: WorkspaceManager, client_id, project_id) -> None:
    workspace = await manager.open_workspace(client_id, project_id=project_id, metadata={"source": "test"})
    assert isinstance(workspace, Workspace)
    assert workspace.client_id == client_id
    assert workspace.active_project_id == project_id
    assert workspace.metadata["source"] == "test"

    again = await manager.open_workspace(client_id)
    assert again.id == workspace.id


@pytest.mark.asyncio
async def test_session_lifecycle(manager: WorkspaceManager, client_id) -> None:
    workspace = await manager.open_workspace(client_id)
    session = await manager.open_session(workspace.id, metadata={"channel": "agent"})
    assert isinstance(session, WorkspaceSession)
    assert session.status == WorkspaceSessionStatus.ACTIVE
    assert session.workspace_id == workspace.id

    refreshed = await manager.get_workspace(workspace.id)
    assert refreshed is not None
    assert refreshed.active_session_id == session.id

    finished = await manager.finish_session(session.id)
    assert finished.status == WorkspaceSessionStatus.FINISHED
    assert finished.finished_at is not None


@pytest.mark.asyncio
async def test_conversation_not_memory(manager: WorkspaceManager, client_id) -> None:
    workspace = await manager.open_workspace(client_id)
    session = await manager.open_session(workspace.id)
    conversation = await manager.ensure_conversation(session.id)
    assert isinstance(conversation, Conversation)
    assert conversation.messages == []

    updated = await manager.append_message(
        conversation.id,
        {"role": "user", "content": "Hello workspace"},
    )
    assert len(updated.messages) == 1

    workspace = await manager.get_workspace(workspace.id)
    assert workspace is not None
    active = await manager.get_active_conversation(workspace)
    assert active is not None
    assert active.messages[0]["content"] == "Hello workspace"


@pytest.mark.asyncio
async def test_workspace_manager_active_pointers(
    manager: WorkspaceManager,
    client_id,
    project_id,
) -> None:
    workspace = await manager.open_workspace(client_id, project_id=project_id)
    session = await manager.open_session(workspace.id)
    await manager.ensure_conversation(session.id)
    workspace = await manager.get_workspace(workspace.id)
    assert workspace is not None

    assert await manager.get_active_client(workspace) == client_id
    assert await manager.get_active_project(workspace) == project_id
    active_session = await manager.get_active_session(workspace)
    assert active_session is not None
    assert await manager.get_active_conversation(workspace) is not None


@pytest.mark.asyncio
async def test_workspace_context_provider(service: WorkspaceService, client_id, project_id) -> None:
    snapshot = await service.open(client_id=client_id, project_id=project_id)
    builder = create_context_builder(workspace_service=service)
    context = await builder.build(
        user_input="Continue work",
        client_id=client_id,
        metadata={"workspace_id": snapshot["workspace_id"]},
    )

    assert context.workspace_context is not None
    assert context.workspace_context["client_id"] == str(client_id)
    assert context.workspace_context["active_project_id"] == str(project_id)
    prioritized = context.to_prioritized_dict()
    assert "workspace_context" in prioritized
    assert list(CONTEXT_PRIORITY) == [
        "user_input",
        "current_task",
        "project_context",
        "client_context",
        "artifact_context",
        "knowledge_context",
        "learning_context",
        "preferences",
        "conversation_history",
    ]


def test_workspace_context_does_not_change_priority() -> None:
    context = ExecutionContext(
        user_input="hello",
        current_task={"title": "task"},
        project_context={"name": "Project"},
        client_context={"name": "Client"},
        artifact_context=[{"name": "doc.pdf"}],
        knowledge_context=[{"title": "Tone"}],
        learning_context=[{"category": "presentation", "rule": "less text"}],
        workspace_context={"workspace_id": "ws-1"},
        preferences={"lang": "ru"},
        conversation_history=[{"role": "user", "content": "hi"}],
    )
    ordered = build_prioritized_context(context)
    assert list(ordered.keys())[: len(CONTEXT_PRIORITY)] == list(CONTEXT_PRIORITY)
    assert ordered["workspace_context"]["workspace_id"] == "ws-1"


@pytest.mark.asyncio
async def test_workspace_node(service: WorkspaceService, client_id, project_id) -> None:
    node = WorkspaceNode(service)
    state = create_initial_state(
        execution_id="exec-ws-1",
        trace_id="trace-ws-1",
        user_input="Open workspace",
        metadata={"client_id": str(client_id), "project_id": str(project_id)},
    )
    update = await node(state)
    assert update["status"] == "workspace_ready"
    assert update["current_step"] == "workspace"
    assert update["workspace_context"]["client_id"] == str(client_id)
    assert update["workspace_context"]["active_session_id"] is not None


@pytest.mark.asyncio
async def test_workspace_node_skips_without_client(service: WorkspaceService) -> None:
    node = WorkspaceNode(service)
    state = create_initial_state(
        execution_id="exec-ws-2",
        trace_id="trace-ws-2",
        user_input="Open workspace",
    )
    update = await node(state)
    assert update["status"] == "workspace_skipped"
    assert update["workspace_context"] is None
