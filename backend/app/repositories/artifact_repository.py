from abc import ABC, abstractmethod
from uuid import UUID

from app.models.artifact import Artifact
from app.schemas.artifact import ArtifactCreate, ArtifactUpdate


class ArtifactRepository(ABC):
    @abstractmethod
    async def create(self, data: ArtifactCreate) -> Artifact:
        ...

    @abstractmethod
    async def get_by_id(self, artifact_id: UUID) -> Artifact | None:
        ...

    @abstractmethod
    async def list_by_project(self, project_id: UUID, skip: int = 0, limit: int = 100) -> list[Artifact]:
        ...

    @abstractmethod
    async def list_all(self, skip: int = 0, limit: int = 100) -> list[Artifact]:
        ...

    @abstractmethod
    async def update(self, artifact_id: UUID, data: ArtifactUpdate) -> Artifact | None:
        ...

    @abstractmethod
    async def delete(self, artifact_id: UUID) -> bool:
        ...
