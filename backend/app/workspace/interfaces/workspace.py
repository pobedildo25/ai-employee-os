from abc import ABC, abstractmethod
from uuid import UUID

from app.workspace.models import Conversation, Workspace, WorkspaceSession


class WorkspaceRepository(ABC):
    """Persistence contract for Workspace, Session, and Conversation."""

    @abstractmethod
    async def save_workspace(self, workspace: Workspace) -> Workspace:
        raise NotImplementedError

    @abstractmethod
    async def get_workspace(self, workspace_id: UUID) -> Workspace | None:
        raise NotImplementedError

    @abstractmethod
    async def get_workspace_by_client(self, client_id: UUID) -> Workspace | None:
        raise NotImplementedError

    @abstractmethod
    async def save_session(self, session: WorkspaceSession) -> WorkspaceSession:
        raise NotImplementedError

    @abstractmethod
    async def get_session(self, session_id: UUID) -> WorkspaceSession | None:
        raise NotImplementedError

    @abstractmethod
    async def save_conversation(self, conversation: Conversation) -> Conversation:
        raise NotImplementedError

    @abstractmethod
    async def get_conversation(self, conversation_id: UUID) -> Conversation | None:
        raise NotImplementedError

    @abstractmethod
    async def get_conversation_by_session(self, session_id: UUID) -> Conversation | None:
        raise NotImplementedError
