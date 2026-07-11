"""API v1 dependency re-exports — use existing DI, no new singletons."""

from app.api.deps import (
    get_agent_runtime,
    get_artifact_service,
    get_client_service,
    get_file_processing_service,
    get_project_service,
    get_session,
    get_task_queue_manager,
    get_task_service,
    get_workspace_service,
)

__all__ = [
    "get_session",
    "get_client_service",
    "get_project_service",
    "get_artifact_service",
    "get_task_service",
    "get_file_processing_service",
    "get_workspace_service",
    "get_task_queue_manager",
    "get_agent_runtime",
]
