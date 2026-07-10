from abc import ABC, abstractmethod
from uuid import UUID

from app.models.artifact_version import ArtifactVersion
from app.schemas.artifact import ArtifactVersionCreate


class ArtifactVersionRepository(ABC):
    @abstractmethod
    async def create_version(
        self,
        artifact_id: UUID,
        version_number: int,
        data: ArtifactVersionCreate,
    ) -> ArtifactVersion:
        ...

    @abstractmethod
    async def get_history(self, artifact_id: UUID) -> list[ArtifactVersion]:
        ...

    @abstractmethod
    async def get_by_version_number(self, artifact_id: UUID, version_number: int) -> ArtifactVersion | None:
        ...
