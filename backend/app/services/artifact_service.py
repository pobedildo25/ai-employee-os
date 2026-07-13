from __future__ import annotations

import logging
import re
from uuid import UUID, uuid4

from app.models.enums import ArtifactStatus
from app.repositories.artifact_repository import ArtifactRepository
from app.repositories.artifact_version_repository import ArtifactVersionRepository
from app.schemas.artifact import (
    ArtifactCreate,
    ArtifactNewVersionRequest,
    ArtifactRead,
    ArtifactUpdate,
    ArtifactUploadRequest,
    ArtifactVersionCreate,
    ArtifactVersionRead,
)
from app.storage.storage_interface import StorageInterface

logger = logging.getLogger(__name__)

_UNSAFE_CHARS = re.compile(r"[^a-zA-Z0-9._-]+")


def sanitize_storage_name(name: str) -> str:
    """Strip path traversal and unsafe characters for object storage keys."""
    if name is None:
        return "artifact"
    cleaned = str(name).replace("\x00", "")
    cleaned = cleaned.replace("\\", "_").replace("/", "_")
    while ".." in cleaned:
        cleaned = cleaned.replace("..", "_")
    cleaned = _UNSAFE_CHARS.sub("_", cleaned).strip("._-")
    return (cleaned or "artifact").lower()[:200]


class ArtifactService:
    def __init__(
        self,
        repository: ArtifactRepository,
        version_repository: ArtifactVersionRepository,
        storage: StorageInterface,
    ) -> None:
        self._repository = repository
        self._version_repository = version_repository
        self._storage = storage

    async def create_artifact(self, data: ArtifactCreate) -> ArtifactRead:
        artifact = await self._repository.create(data)
        return ArtifactRead.model_validate(artifact)

    async def upload_artifact(
        self,
        request: ArtifactUploadRequest,
        file_data: bytes,
        mime_type: str | None = None,
    ) -> ArtifactRead:
        storage_path = self._build_storage_path(request.client_id, request.project_id, request.name)
        await self._storage.upload(storage_path, file_data, mime_type)

        artifact_data = ArtifactCreate(
            client_id=request.client_id,
            project_id=request.project_id,
            name=request.name,
            artifact_type=request.artifact_type,
            description=request.description,
            status=ArtifactStatus.COMPLETED,
            storage_path=storage_path,
            mime_type=mime_type,
            size=len(file_data),
            metadata=request.metadata,
            created_by=request.created_by,
        )
        try:
            artifact = await self._repository.create(artifact_data)
            version_data = ArtifactVersionCreate(
                storage_path=storage_path,
                metadata=request.metadata,
                created_by=request.created_by,
                change_description="Initial upload",
            )
            await self._version_repository.create_version(artifact.id, 1, version_data)
        except Exception:
            await self._compensate_storage_delete(storage_path)
            raise

        refreshed = await self._repository.get_by_id(artifact.id)
        return ArtifactRead.model_validate(refreshed)

    async def create_new_version(
        self,
        artifact_id: UUID,
        request: ArtifactNewVersionRequest,
        file_data: bytes,
        mime_type: str | None = None,
    ) -> ArtifactVersionRead:
        artifact = await self._repository.get_by_id(artifact_id)
        if artifact is None:
            raise ValueError(f"Artifact {artifact_id} not found")

        latest = await self._repository.get_latest_version(artifact_id)
        next_version = (latest.version_number + 1) if latest else 1

        storage_path = self._build_version_storage_path(
            artifact.client_id,
            artifact.project_id,
            artifact.name,
            next_version,
        )
        await self._storage.upload(storage_path, file_data, mime_type)

        version_data = ArtifactVersionCreate(
            storage_path=storage_path,
            metadata=request.metadata,
            created_by=request.created_by,
            change_description=request.change_description,
        )
        try:
            version = await self._version_repository.create_version(artifact_id, next_version, version_data)
            await self._repository.update(
                artifact_id,
                ArtifactUpdate(
                    storage_path=storage_path,
                    mime_type=mime_type,
                    size=len(file_data),
                    status=ArtifactStatus.COMPLETED,
                    metadata=request.metadata,
                ),
            )
        except Exception:
            await self._compensate_storage_delete(storage_path)
            raise

        return ArtifactVersionRead.model_validate(version)

    async def get_by_id(self, artifact_id: UUID) -> ArtifactRead | None:
        artifact = await self._repository.get_by_id(artifact_id)
        return ArtifactRead.model_validate(artifact) if artifact else None

    async def get_artifact_history(self, artifact_id: UUID) -> list[ArtifactVersionRead]:
        history = await self._version_repository.get_history(artifact_id)
        return [ArtifactVersionRead.model_validate(item) for item in history]

    async def get_latest_version(self, artifact_id: UUID) -> ArtifactVersionRead | None:
        version = await self._repository.get_latest_version(artifact_id)
        return ArtifactVersionRead.model_validate(version) if version else None

    async def list_by_project(self, project_id: UUID, skip: int = 0, limit: int = 100) -> list[ArtifactRead]:
        artifacts = await self._repository.list_by_project(project_id, skip=skip, limit=limit)
        return [ArtifactRead.model_validate(artifact) for artifact in artifacts]

    async def list_by_client(self, client_id: UUID, skip: int = 0, limit: int = 100) -> list[ArtifactRead]:
        artifacts = await self._repository.list_by_client(client_id, skip=skip, limit=limit)
        return [ArtifactRead.model_validate(artifact) for artifact in artifacts]

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[ArtifactRead]:
        artifacts = await self._repository.list_all(skip=skip, limit=limit)
        return [ArtifactRead.model_validate(artifact) for artifact in artifacts]

    async def update(self, artifact_id: UUID, data: ArtifactUpdate) -> ArtifactRead | None:
        artifact = await self._repository.update(artifact_id, data)
        return ArtifactRead.model_validate(artifact) if artifact else None

    async def delete(self, artifact_id: UUID) -> bool:
        artifact = await self._repository.get_by_id(artifact_id)
        if artifact is None:
            return False

        versions = await self._version_repository.get_history(artifact_id)
        for version in versions:
            await self._best_effort_storage_delete(version.storage_path)
        if artifact.storage_path:
            await self._best_effort_storage_delete(artifact.storage_path)

        return await self._repository.delete(artifact_id)

    async def _compensate_storage_delete(self, storage_path: str) -> None:
        try:
            deleted = await self._storage.delete(storage_path)
            if deleted:
                logger.info("compensated MinIO object after DB failure | path=%s", storage_path)
            else:
                logger.warning("compensation delete returned false | path=%s", storage_path)
        except Exception as exc:
            logger.exception(
                "compensation storage delete failed | path=%s error=%s",
                storage_path,
                exc,
            )

    async def _best_effort_storage_delete(self, storage_path: str) -> None:
        try:
            deleted = await self._storage.delete(storage_path)
            if not deleted:
                logger.warning("best-effort storage delete returned false | path=%s", storage_path)
        except Exception as exc:
            logger.warning(
                "best-effort storage delete failed | path=%s error=%s",
                storage_path,
                exc,
            )

    def _build_storage_path(self, client_id: UUID, project_id: UUID, name: str) -> str:
        safe_name = sanitize_storage_name(name)
        return f"{client_id}/{project_id}/{safe_name}/{uuid4()}"

    def _build_version_storage_path(
        self,
        client_id: UUID,
        project_id: UUID,
        name: str,
        version_number: int,
    ) -> str:
        safe_name = sanitize_storage_name(name)
        return f"{client_id}/{project_id}/{safe_name}/v{version_number}/{uuid4()}"
