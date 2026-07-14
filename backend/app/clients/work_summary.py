"""Answer "что сделано по клиенту X" from the database.

Reads the client's projects and artifacts and formats a concise chat answer, so
the user can ask what work exists for a client without leaving the dialogue.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from app.clients.name_extractor import extract_subject_heuristic
from app.repositories.artifact_repository import ArtifactRepository
from app.repositories.client_repository import ClientRepository
from app.repositories.project_repository import ProjectRepository

logger = logging.getLogger(__name__)

_STATUS_TRIGGERS = (
    "что сделано",
    "что сделал",
    "что делали",
    "что готово",
    "что по клиент",
    "что у нас по",
    "статус по",
    "статус клиент",
    "истори",
    "какие проект",
    "покажи проект",
    "что мы делали",
    "что уже сделан",
)


_PROPER_NOUN = re.compile(r"[«\"']?([A-ZА-ЯЁ][\wА-Яа-яЁё&.\-]{1,40})")

# Capitalized query words that are not client names.
_NAME_STOPWORDS = frozenset(
    {
        "что",
        "какие",
        "какой",
        "покажи",
        "статус",
        "история",
        "клиент",
        "клиента",
        "клиенту",
        "проект",
        "проекты",
        "бренд",
        "компания",
        "компании",
    }
)


def detect_client_status_query(text: str) -> str | None:
    """Return the client name when the message asks about work done for a client."""
    if not text:
        return None
    lowered = text.lower()
    if not any(trigger in lowered for trigger in _STATUS_TRIGGERS):
        return None

    name = extract_subject_heuristic(text)
    if name:
        return name

    # Fallback: the trailing proper noun that is not a query keyword.
    for token in reversed(_PROPER_NOUN.findall(text)):
        if token.casefold() not in _NAME_STOPWORDS:
            return token.strip("«»\"'")
    return None


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
