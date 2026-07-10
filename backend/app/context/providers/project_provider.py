from typing import Any

from app.context.models import ContextRequest
from app.context.providers.base import ContextProvider
from app.repositories.project_repository import ProjectRepository


class ProjectContextProvider(ContextProvider):
    name = "project"

    def __init__(self, repository: ProjectRepository) -> None:
        self._repository = repository

    async def fetch(self, request: ContextRequest) -> dict[str, Any]:
        if request.project_id is None:
            return {}

        project = await self._repository.get_by_id(request.project_id)
        if project is None:
            return {}

        return {
            "project_context": {
                "id": str(project.id),
                "client_id": str(project.client_id),
                "name": project.name,
                "description": project.description,
                "status": project.status,
            }
        }
