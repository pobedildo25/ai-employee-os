"""Answer client work history from the database (tool/service — not a router).

Must not be used for keyword / regex Product Decision. Executive owns intent;
callers may use ``summarize`` only after a Product Decision that needs history.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.repositories.artifact_repository import ArtifactRepository
from app.repositories.client_repository import ClientRepository
from app.repositories.project_repository import ProjectRepository

logger = logging.getLogger(__name__)


@dataclass
class ClientWorkSummary:
    name: str
    projects: list[dict] = field(default_factory=list)
    artifacts: list[dict] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.projects and not self.artifacts


class ClientWorkSummaryService:
    def __init__(
        self,
        client_repository: ClientRepository,
        project_repository: ProjectRepository | None = None,
        artifact_repository: ArtifactRepository | None = None,
    ) -> None:
        self._clients = client_repository
        self._projects = project_repository
        self._artifacts = artifact_repository

    async def summarize(self, name: str) -> ClientWorkSummary | None:
        client = await self._clients.find_by_name(name)
        if client is None:
            return None

        projects: list[dict] = []
        artifacts: list[dict] = []
        if self._projects is not None:
            project_models = await self._projects.list_by_client(client.id, limit=50)
            for project in project_models:
                projects.append(
                    {
                        "name": getattr(project, "name", "проект"),
                        "status": getattr(project, "status", ""),
                    }
                )
                if self._artifacts is not None:
                    for artifact in await self._artifacts.list_by_project(project.id, limit=50):
                        artifacts.append(
                            {
                                "name": getattr(artifact, "name", "документ"),
                                "type": getattr(artifact, "artifact_type", ""),
                                "status": _status_value(getattr(artifact, "status", "")),
                            }
                        )

        return ClientWorkSummary(
            name=getattr(client, "name", name),
            projects=projects,
            artifacts=artifacts,
        )

    @staticmethod
    def format_reply(summary: ClientWorkSummary) -> str:
        if summary.is_empty:
            return f"По клиенту «{summary.name}» пока нет проектов и документов в базе."

        lines = [f"Что есть по клиенту «{summary.name}»:"]
        if summary.projects:
            lines.append(f"\nПроекты ({len(summary.projects)}):")
            for project in summary.projects[:15]:
                status = f" — {project['status']}" if project.get("status") else ""
                lines.append(f"• {project['name']}{status}")
        if summary.artifacts:
            lines.append(f"\nДокументы ({len(summary.artifacts)}):")
            for artifact in summary.artifacts[:20]:
                meta = " ".join(
                    part
                    for part in (
                        f"[{artifact['type']}]" if artifact.get("type") else "",
                        f"— {artifact['status']}" if artifact.get("status") else "",
                    )
                    if part
                )
                lines.append(f"• {artifact['name']} {meta}".rstrip())
        return "\n".join(lines)


def _status_value(status: object) -> str:
    return getattr(status, "value", str(status) if status else "")
