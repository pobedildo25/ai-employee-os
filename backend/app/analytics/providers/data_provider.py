from typing import Any
from uuid import UUID

from app.analytics.interfaces.analytics import AnalyticsDataProvider
from app.analytics.models import AnalyticsDataset, AnalyticsRequest
from app.clients.classification import is_telegram_user_client
from app.repositories.artifact_repository import ArtifactRepository
from app.repositories.client_repository import ClientRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository


class CompositeAnalyticsDataProvider(AnalyticsDataProvider):
    """Aggregates read-only fragments from optional repositories/context."""

    name = "composite"

    def __init__(
        self,
        *,
        client_repository: ClientRepository | None = None,
        project_repository: ProjectRepository | None = None,
        artifact_repository: ArtifactRepository | None = None,
        task_repository: TaskRepository | None = None,
    ) -> None:
        self._clients = client_repository
        self._projects = project_repository
        self._artifacts = artifact_repository
        self._tasks = task_repository

    async def fetch(self, request: AnalyticsRequest) -> dict[str, Any]:
        dataset = await self.collect(request)
        return dataset.model_dump(mode="json")

    async def collect(self, request: AnalyticsRequest) -> AnalyticsDataset:
        context = request.context or {}
        dataset = AnalyticsDataset(
            clients=list(context.get("clients") or []),
            projects=list(context.get("projects") or []),
            tasks=list(context.get("tasks") or []),
            artifacts=list(context.get("artifacts") or []),
            executions=list(context.get("executions") or context.get("execution_traces") or []),
            quality_results=list(context.get("quality_results") or []),
            revisions=list(context.get("revisions") or context.get("revision_history") or []),
            client_intelligence=dict(
                context.get("client_intelligence_context")
                or context.get("client_intelligence")
                or {}
            ),
            learning_rules=list(
                request.learning_rules
                or context.get("learning_context")
                or context.get("learning_rules")
                or []
            ),
        )
        sources: list[str] = []

        client_id = _as_uuid(request.client_id)
        project_id = _as_uuid(request.project_id)

        if client_id and self._clients is not None and not dataset.clients:
            client = await self._clients.get_by_id(client_id)
            if client is not None and is_telegram_user_client(client):
                dataset.sources_used = ["skipped_telegram_user"]
                return dataset
            if client is not None:
                dataset.clients = [
                    {
                        "id": str(client.id),
                        "name": client.name,
                        "description": client.description,
                    }
                ]
                sources.append("clients")

        if client_id and self._projects is not None and not dataset.projects:
            projects = await self._projects.list_by_client(client_id, skip=0, limit=100)
            dataset.projects = [_project_dict(p) for p in projects]
            sources.append("projects")
        elif project_id and self._projects is not None and not dataset.projects:
            project = await self._projects.get_by_id(project_id)
            if project is not None:
                dataset.projects = [_project_dict(project)]
                sources.append("projects")

        project_ids = [str(p.get("id")) for p in dataset.projects if p.get("id")]
        if project_id:
            project_ids = [str(project_id)]

        if self._artifacts is not None and not dataset.artifacts and project_ids:
            artifacts: list[dict[str, Any]] = []
            for pid in project_ids[:20]:
                uid = _as_uuid(pid)
                if uid is None:
                    continue
                items = await self._artifacts.list_by_project(uid, skip=0, limit=100)
                artifacts.extend(_artifact_dict(a) for a in items)
            dataset.artifacts = artifacts
            if artifacts:
                sources.append("artifacts")

        if self._tasks is not None and not dataset.tasks and project_ids:
            tasks: list[dict[str, Any]] = []
            for pid in project_ids[:20]:
                uid = _as_uuid(pid)
                if uid is None:
                    continue
                items = await self._tasks.list_by_project(uid, skip=0, limit=100)
                tasks.extend(_task_dict(t) for t in items)
            dataset.tasks = tasks
            if tasks:
                sources.append("tasks")

        if dataset.executions:
            sources.append("executions")
        if dataset.quality_results:
            sources.append("quality")
        if dataset.revisions:
            sources.append("revisions")
        if dataset.client_intelligence:
            sources.append("client_intelligence")
        if dataset.learning_rules:
            sources.append("learning")
        if context:
            sources.append("context")

        dataset.sources_used = list(dict.fromkeys(sources))
        return dataset


def _project_dict(project: Any) -> dict[str, Any]:
    return {
        "id": str(project.id),
        "client_id": str(project.client_id),
        "name": project.name,
        "description": project.description,
        "status": getattr(project.status, "value", project.status),
        "created_at": getattr(project, "created_at", None),
        "updated_at": getattr(project, "updated_at", None),
    }


def _artifact_dict(artifact: Any) -> dict[str, Any]:
    return {
        "id": str(artifact.id),
        "project_id": str(artifact.project_id),
        "client_id": str(artifact.client_id),
        "name": artifact.name,
        "artifact_type": artifact.artifact_type,
        "status": getattr(artifact.status, "value", str(artifact.status)),
    }


def _task_dict(task: Any) -> dict[str, Any]:
    return {
        "id": str(task.id),
        "project_id": str(getattr(task, "project_id", "")),
        "name": getattr(task, "name", None) or getattr(task, "title", None),
        "status": getattr(getattr(task, "status", None), "value", getattr(task, "status", None)),
    }


def _as_uuid(value: UUID | str | None) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except ValueError:
        return None
