from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workspace import ConversationRecord, WorkspaceRecord, WorkspaceSessionRecord
from app.workspace.interfaces.workspace import WorkspaceRepository
from app.workspace.models import Conversation, Workspace, WorkspaceSession, WorkspaceSessionStatus


class InMemoryWorkspaceRepository(WorkspaceRepository):
    """In-memory workspace store for tests and local development."""

    def __init__(self) -> None:
        self._workspaces: dict[UUID, Workspace] = {}
        self._sessions: dict[UUID, WorkspaceSession] = {}
        self._conversations: dict[UUID, Conversation] = {}
        self._client_index: dict[UUID, UUID] = {}
        self._session_conversation: dict[UUID, UUID] = {}

    async def save_workspace(self, workspace: Workspace) -> Workspace:
        workspace.updated_at = datetime.now()
        self._workspaces[workspace.id] = workspace
        self._client_index[workspace.client_id] = workspace.id
        return workspace

    async def get_workspace(self, workspace_id: UUID) -> Workspace | None:
        return self._workspaces.get(workspace_id)

    async def get_workspace_by_client(self, client_id: UUID) -> Workspace | None:
        workspace_id = self._client_index.get(client_id)
        if workspace_id is None:
            return None
        return self._workspaces.get(workspace_id)

    async def save_session(self, session: WorkspaceSession) -> WorkspaceSession:
        self._sessions[session.id] = session
        return session

    async def get_session(self, session_id: UUID) -> WorkspaceSession | None:
        return self._sessions.get(session_id)

    async def save_conversation(self, conversation: Conversation) -> Conversation:
        conversation.updated_at = datetime.now()
        self._conversations[conversation.id] = conversation
        self._session_conversation[conversation.session_id] = conversation.id
        return conversation

    async def get_conversation(self, conversation_id: UUID) -> Conversation | None:
        return self._conversations.get(conversation_id)

    async def get_conversation_by_session(self, session_id: UUID) -> Conversation | None:
        conversation_id = self._session_conversation.get(session_id)
        if conversation_id is None:
            return None
        return self._conversations.get(conversation_id)


class PostgresWorkspaceRepository(WorkspaceRepository):
    """PostgreSQL-backed workspace repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_workspace(self, workspace: Workspace) -> Workspace:
        record = await self._session.get(WorkspaceRecord, workspace.id)
        if record is None:
            record = WorkspaceRecord(id=workspace.id, client_id=workspace.client_id)
            self._session.add(record)
        record.client_id = workspace.client_id
        record.active_project_id = workspace.active_project_id
        record.active_session_id = workspace.active_session_id
        record.active_task_id = workspace.active_task_id
        record.active_artifact_id = workspace.active_artifact_id
        record.metadata_ = workspace.metadata
        await self._session.flush()
        return workspace

    async def get_workspace(self, workspace_id: UUID) -> Workspace | None:
        record = await self._session.get(WorkspaceRecord, workspace_id)
        return _to_workspace(record) if record else None

    async def get_workspace_by_client(self, client_id: UUID) -> Workspace | None:
        stmt = select(WorkspaceRecord).where(WorkspaceRecord.client_id == client_id).limit(1)
        result = await self._session.execute(stmt)
        record = result.scalar_one_or_none()
        return _to_workspace(record) if record else None

    async def save_session(self, session: WorkspaceSession) -> WorkspaceSession:
        record = await self._session.get(WorkspaceSessionRecord, session.id)
        if record is None:
            record = WorkspaceSessionRecord(
                id=session.id,
                workspace_id=session.workspace_id,
                started_at=session.started_at,
            )
            self._session.add(record)
        record.workspace_id = session.workspace_id
        record.status = session.status.value
        record.started_at = session.started_at
        record.finished_at = session.finished_at
        record.metadata_ = session.metadata
        await self._session.flush()
        return session

    async def get_session(self, session_id: UUID) -> WorkspaceSession | None:
        record = await self._session.get(WorkspaceSessionRecord, session_id)
        return _to_session(record) if record else None

    async def save_conversation(self, conversation: Conversation) -> Conversation:
        record = await self._session.get(ConversationRecord, conversation.id)
        if record is None:
            record = ConversationRecord(id=conversation.id, session_id=conversation.session_id)
            self._session.add(record)
        record.session_id = conversation.session_id
        record.messages = conversation.messages
        record.summary = conversation.summary
        record.metadata_ = conversation.metadata
        await self._session.flush()
        return conversation

    async def get_conversation(self, conversation_id: UUID) -> Conversation | None:
        record = await self._session.get(ConversationRecord, conversation_id)
        return _to_conversation(record) if record else None

    async def get_conversation_by_session(self, session_id: UUID) -> Conversation | None:
        stmt = select(ConversationRecord).where(ConversationRecord.session_id == session_id).limit(1)
        result = await self._session.execute(stmt)
        record = result.scalar_one_or_none()
        return _to_conversation(record) if record else None


def _to_workspace(record: WorkspaceRecord) -> Workspace:
    return Workspace(
        id=record.id,
        client_id=record.client_id,
        active_project_id=record.active_project_id,
        active_session_id=record.active_session_id,
        active_task_id=record.active_task_id,
        active_artifact_id=record.active_artifact_id,
        metadata=record.metadata_ or {},
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _to_session(record: WorkspaceSessionRecord) -> WorkspaceSession:
    return WorkspaceSession(
        id=record.id,
        workspace_id=record.workspace_id,
        status=WorkspaceSessionStatus(record.status),
        started_at=record.started_at,
        finished_at=record.finished_at,
        metadata=record.metadata_ or {},
    )


def _to_conversation(record: ConversationRecord) -> Conversation:
    return Conversation(
        id=record.id,
        session_id=record.session_id,
        messages=list(record.messages or []),
        summary=record.summary,
        metadata=record.metadata_ or {},
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
