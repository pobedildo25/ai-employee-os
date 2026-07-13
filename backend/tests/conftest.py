from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

pytest_plugins = ["tests.conftest_file_processing"]

from app.models.artifact import Artifact
from app.models.artifact_version import ArtifactVersion
from app.models.enums import ArtifactStatus
from app.schemas.artifact import ArtifactCreate, ArtifactNewVersionRequest, ArtifactUploadRequest
from app.services.artifact_service import ArtifactService


class InMemoryStorage:
    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    async def upload(self, path: str, data: bytes, content_type: str | None = None) -> str:
        self._objects[path] = data
        return path

    async def download(self, path: str) -> bytes:
        return self._objects[path]

    async def delete(self, path: str) -> bool:
        return self._objects.pop(path, None) is not None

    async def exists(self, path: str) -> bool:
        return path in self._objects


class FakeArtifactRepository:
    def __init__(self) -> None:
        self._artifacts: dict[UUID, Artifact] = {}
        self._versions: dict[UUID, list[ArtifactVersion]] = {}

    async def create(self, data: ArtifactCreate) -> Artifact:
        artifact = Artifact(
            id=uuid4(),
            client_id=data.client_id,
            project_id=data.project_id,
            name=data.name,
            artifact_type=data.artifact_type,
            description=data.description,
            status=data.status,
            storage_path=data.storage_path,
            mime_type=data.mime_type,
            size=data.size,
            metadata_=data.metadata,
            created_by=data.created_by,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self._artifacts[artifact.id] = artifact
        self._versions[artifact.id] = []
        return artifact

    async def get_by_id(self, artifact_id: UUID) -> Artifact | None:
        return self._artifacts.get(artifact_id)

    async def list_by_project(self, project_id: UUID, skip: int = 0, limit: int = 100) -> list[Artifact]:
        return [a for a in self._artifacts.values() if a.project_id == project_id]

    async def list_by_client(self, client_id: UUID, skip: int = 0, limit: int = 100) -> list[Artifact]:
        return [a for a in self._artifacts.values() if a.client_id == client_id]

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[Artifact]:
        return list(self._artifacts.values())

    async def update(self, artifact_id: UUID, data) -> Artifact | None:
        artifact = self._artifacts.get(artifact_id)
        if artifact is None:
            return None
        update_data = data.model_dump(exclude_unset=True)
        if "metadata" in update_data:
            artifact.metadata_ = update_data.pop("metadata")
        for field, value in update_data.items():
            setattr(artifact, field, value)
        return artifact

    async def delete(self, artifact_id: UUID) -> bool:
        return self._artifacts.pop(artifact_id, None) is not None

    async def get_versions(self, artifact_id: UUID) -> list[ArtifactVersion]:
        return self._versions.get(artifact_id, [])

    async def get_latest_version(self, artifact_id: UUID) -> ArtifactVersion | None:
        versions = self._versions.get(artifact_id, [])
        return versions[-1] if versions else None


class FakeArtifactVersionRepository:
    def __init__(self, artifact_repo: FakeArtifactRepository) -> None:
        self._artifact_repo = artifact_repo

    async def create_version(self, artifact_id: UUID, version_number: int, data) -> ArtifactVersion:
        version = ArtifactVersion(
            id=uuid4(),
            artifact_id=artifact_id,
            version_number=version_number,
            storage_path=data.storage_path,
            metadata_=data.metadata,
            created_by=data.created_by,
            change_description=data.change_description,
            created_at=datetime.now(timezone.utc),
        )
        self._artifact_repo._versions.setdefault(artifact_id, []).append(version)
        return version

    async def get_history(self, artifact_id: UUID) -> list[ArtifactVersion]:
        return self._artifact_repo._versions.get(artifact_id, [])

    async def get_by_version_number(self, artifact_id: UUID, version_number: int) -> ArtifactVersion | None:
        for version in self._artifact_repo._versions.get(artifact_id, []):
            if version.version_number == version_number:
                return version
        return None


@pytest.fixture
def artifact_service() -> ArtifactService:
    artifact_repo = FakeArtifactRepository()
    version_repo = FakeArtifactVersionRepository(artifact_repo)
    storage = InMemoryStorage()
    return ArtifactService(artifact_repo, version_repo, storage)


@pytest.fixture
def ids() -> tuple[UUID, UUID]:
    return uuid4(), uuid4()
