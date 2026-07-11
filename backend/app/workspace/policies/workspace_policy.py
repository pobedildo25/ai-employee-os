from app.workspace.models import Workspace, WorkspaceSession, WorkspaceSessionStatus


def can_open_session(workspace: Workspace) -> bool:
    return workspace.client_id is not None


def is_session_active(session: WorkspaceSession) -> bool:
    return session.status == WorkspaceSessionStatus.ACTIVE and session.finished_at is None


def can_attach_conversation(session: WorkspaceSession) -> bool:
    return is_session_active(session)
