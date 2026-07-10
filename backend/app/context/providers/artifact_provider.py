from typing import Any

from app.context.models import ContextRequest
from app.context.providers.base import ContextProvider
from app.repositories.artifact_repository import ArtifactRepository


class ArtifactContextProvider(ContextProvider):
    name = "artifact"

    def __init__(self, repository: ArtifactRepository) -> None:
        self._repository = repository

    async def fetch(self, request: ContextRequest) -> dict[str, Any]:
        if request.project_id is None:
            return {}

        artifacts = await self._repository.list_by_project(request.project_id, limit=20)
        if not artifacts:
            return {}

        return {
            "artifact_context": [
                {
                    "id": str(artifact.id),
                    "name": artifact.name,
                    "artifact_type": artifact.artifact_type,
                    "description": artifact.description,
                    "status": artifact.status.value if hasattr(artifact.status, "value") else str(artifact.status),
                    "mime_type": artifact.mime_type,
                }
                for artifact in artifacts
            ]
        }
