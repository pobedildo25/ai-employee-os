from datetime import datetime
from typing import Any
from uuid import UUID

from app.workspace.interfaces.workspace import WorkspaceRepository
from app.workspace.models import Conversation, Workspace, WorkspaceSession, WorkspaceSessionStatus
from app.workspace.policies.workspace_policy import can_attach_conversation, can_open_session
from app.workspace.repositories.workspace_repository import InMemoryWorkspaceRepository


class WorkspaceManager:
    """Infrastructure manager for AI Employee workspaces — no business logic."""

    def __init__(self, repository: WorkspaceRepository | None = None) -> None:
        self._repository = repository or InMemoryWorkspaceRepository()

    async def open_workspace(
        self,
        client_id: UUID,
        *,
        project_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Workspace:
        existing = await self._repository.get_workspace_by_client(client_id)
        if existing is not None:
            if project_id is not None:
                existing.active_project_id = project_id
            if metadata:
                existing.metadata.update(metadata)
            return await self._repository.save_workspace(existing)

        workspace = Workspace(
            client_id=client_id,
            active_project_id=project_id,
            metadata=metadata or {},
        )
        return await self._repository.save_workspace(workspace)

    async def open_session(
        self,
        workspace_id: UUID,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> WorkspaceSession:
        workspace = await self._repository.get_workspace(workspace_id)
        if workspace is None:
            raise ValueError(f"Workspace not found: {workspace_id}")
        if not can_open_session(workspace):
            raise ValueError("Workspace cannot open a session without client_id")

        session = WorkspaceSession(
            workspace_id=workspace_id,
            status=WorkspaceSessionStatus.ACTIVE,
            metadata=metadata or {},
        )
        saved = await self._repository.save_session(session)
        workspace.active_session_id = saved.id
        await self._repository.save_workspace(workspace)
        return saved

    async def finish_session(self, session_id: UUID) -> WorkspaceSession:
        session = await self._repository.get_session(session_id)
        if session is None:
            raise ValueError(f"Session not found: {session_id}")
        session.status = WorkspaceSessionStatus.FINISHED
        session.finished_at = datetime.now()
        return await self._repository.save_session(session)

    async def get_workspace(self, workspace_id: UUID) -> Workspace | None:
        return await self._repository.get_workspace(workspace_id)

    async def get_workspace_by_client(self, client_id: UUID) -> Workspace | None:
        return await self._repository.get_workspace_by_client(client_id)

    async def get_active_client(self, workspace: Workspace) -> UUID:
        return workspace.client_id

    async def get_active_project(self, workspace: Workspace) -> UUID | None:
        return workspace.active_project_id

    async def get_active_session(self, workspace: Workspace) -> WorkspaceSession | None:
        if workspace.active_session_id is None:
            return None
        return await self._repository.get_session(workspace.active_session_id)

    async def get_active_conversation(self, workspace: Workspace) -> Conversation | None:
        if workspace.active_session_id is None:
            return None
        return await self._repository.get_conversation_by_session(workspace.active_session_id)

    async def ensure_conversation(self, session_id: UUID) -> Conversation:
        session = await self._repository.get_session(session_id)
        if session is None:
            raise ValueError(f"Session not found: {session_id}")
        if not can_attach_conversation(session):
            raise ValueError("Conversation requires an active session")

        existing = await self._repository.get_conversation_by_session(session_id)
        if existing is not None:
            return existing

        conversation = Conversation(session_id=session_id)
        return await self._repository.save_conversation(conversation)

    async def set_active_project(self, workspace_id: UUID, project_id: UUID | None) -> Workspace:
        workspace = await self._require_workspace(workspace_id)
        workspace.active_project_id = project_id
        return await self._repository.save_workspace(workspace)

    async def set_active_task(self, workspace_id: UUID, task_id: UUID | None) -> Workspace:
        workspace = await self._require_workspace(workspace_id)
        workspace.active_task_id = task_id
        return await self._repository.save_workspace(workspace)

    async def set_active_artifact(self, workspace_id: UUID, artifact_id: UUID | None) -> Workspace:
        workspace = await self._require_workspace(workspace_id)
        workspace.active_artifact_id = artifact_id
        return await self._repository.save_workspace(workspace)

    async def append_message(
        self,
        conversation_id: UUID,
        message: dict[str, Any],
    ) -> Conversation:
        conversation = await self._repository.get_conversation(conversation_id)
        if conversation is None:
            raise ValueError(f"Conversation not found: {conversation_id}")
        conversation.messages.append(message)
        return await self._repository.save_conversation(conversation)

    async def _require_workspace(self, workspace_id: UUID) -> Workspace:
        workspace = await self._repository.get_workspace(workspace_id)
        if workspace is None:
            raise ValueError(f"Workspace not found: {workspace_id}")
        return workspace
