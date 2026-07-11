from typing import Any
from uuid import UUID

from app.workspace.manager import WorkspaceManager
from app.workspace.models import Conversation, Workspace, WorkspaceSession


class WorkspaceService:
    """Assembles workspace snapshots for context and runtime nodes."""

    def __init__(self, manager: WorkspaceManager | None = None) -> None:
        self._manager = manager or WorkspaceManager()

    @property
    def manager(self) -> WorkspaceManager:
        return self._manager

    async def open(
        self,
        *,
        client_id: UUID,
        project_id: UUID | None = None,
        task_id: UUID | None = None,
        artifact_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
        open_session: bool = True,
    ) -> dict[str, Any]:
        workspace = await self._manager.open_workspace(
            client_id,
            project_id=project_id,
            metadata=metadata,
        )
        if task_id is not None:
            workspace = await self._manager.set_active_task(workspace.id, task_id)
        if artifact_id is not None:
            workspace = await self._manager.set_active_artifact(workspace.id, artifact_id)

        session: WorkspaceSession | None = None
        conversation: Conversation | None = None
        if open_session:
            session = await self._manager.open_session(workspace.id)
            conversation = await self._manager.ensure_conversation(session.id)
            workspace = await self._manager.get_workspace(workspace.id) or workspace

        return self.build_snapshot(workspace, session=session, conversation=conversation)

    async def get_snapshot(self, workspace_id: UUID) -> dict[str, Any] | None:
        workspace = await self._manager.get_workspace(workspace_id)
        if workspace is None:
            return None
        session = await self._manager.get_active_session(workspace)
        conversation = await self._manager.get_active_conversation(workspace)
        return self.build_snapshot(workspace, session=session, conversation=conversation)

    async def get_snapshot_for_client(self, client_id: UUID) -> dict[str, Any] | None:
        workspace = await self._manager.get_workspace_by_client(client_id)
        if workspace is None:
            return None
        return await self.get_snapshot(workspace.id)

    def build_snapshot(
        self,
        workspace: Workspace,
        *,
        session: WorkspaceSession | None = None,
        conversation: Conversation | None = None,
    ) -> dict[str, Any]:
        return {
            "workspace_id": str(workspace.id),
            "client_id": str(workspace.client_id),
            "active_project_id": str(workspace.active_project_id) if workspace.active_project_id else None,
            "active_session_id": str(workspace.active_session_id) if workspace.active_session_id else None,
            "active_task_id": str(workspace.active_task_id) if workspace.active_task_id else None,
            "active_artifact_id": str(workspace.active_artifact_id) if workspace.active_artifact_id else None,
            "active_background_tasks": [str(task_id) for task_id in workspace.active_background_tasks],
            "session": session.model_dump(mode="json") if session else None,
            "conversation": {
                "id": str(conversation.id),
                "session_id": str(conversation.session_id),
                "message_count": len(conversation.messages),
                "summary": conversation.summary,
            }
            if conversation
            else None,
            "metadata": workspace.metadata,
        }
