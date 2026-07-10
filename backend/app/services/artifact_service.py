from uuid import UUID

from app.repositories.artifact_repository import ArtifactRepository
from app.schemas.artifact import ArtifactCreate, ArtifactRead, ArtifactUpdate


class ArtifactService:
    def __init__(self, repository: ArtifactRepository) -> None:
        self._repository = repository

    async def create(self, data: ArtifactCreate) -> ArtifactRead:
        artifact = await self._repository.create(data)
        return ArtifactRead.model_validate(artifact)

    async def get_by_id(self, artifact_id: UUID) -> ArtifactRead | None:
        artifact = await self._repository.get_by_id(artifact_id)
        return ArtifactRead.model_validate(artifact) if artifact else None

    async def list_by_project(self, project_id: UUID, skip: int = 0, limit: int = 100) -> list[ArtifactRead]:
        artifacts = await self._repository.list_by_project(project_id, skip=skip, limit=limit)
        return [ArtifactRead.model_validate(artifact) for artifact in artifacts]

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[ArtifactRead]:
        artifacts = await self._repository.list_all(skip=skip, limit=limit)
        return [ArtifactRead.model_validate(artifact) for artifact in artifacts]

    async def update(self, artifact_id: UUID, data: ArtifactUpdate) -> ArtifactRead | None:
        artifact = await self._repository.update(artifact_id, data)
        return ArtifactRead.model_validate(artifact) if artifact else None

    async def delete(self, artifact_id: UUID) -> bool:
        return await self._repository.delete(artifact_id)
