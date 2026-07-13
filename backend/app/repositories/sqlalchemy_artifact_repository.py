from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.artifact import Artifact
from app.models.artifact_version import ArtifactVersion
from app.repositories.artifact_repository import ArtifactRepository
from app.schemas.artifact import ArtifactCreate, ArtifactUpdate


class SQLAlchemyArtifactRepository(ArtifactRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: ArtifactCreate) -> Artifact:
        artifact = Artifact(
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
        )
        self._session.add(artifact)
        await self._session.flush()
        await self._session.refresh(artifact)
        return artifact

    async def get_by_id(self, artifact_id: UUID) -> Artifact | None:
        result = await self._session.execute(
            select(Artifact)
            .where(Artifact.id == artifact_id)
            .options(selectinload(Artifact.versions))
        )
        return result.scalar_one_or_none()

    async def list_by_project(self, project_id: UUID, skip: int = 0, limit: int = 100) -> list[Artifact]:
        result = await self._session.execute(
            select(Artifact)
            .where(Artifact.project_id == project_id)
            .offset(skip)
            .limit(limit)
            .order_by(Artifact.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_by_client(self, client_id: UUID, skip: int = 0, limit: int = 100) -> list[Artifact]:
        result = await self._session.execute(
            select(Artifact)
            .where(Artifact.client_id == client_id)
            .offset(skip)
            .limit(limit)
            .order_by(Artifact.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[Artifact]:
        result = await self._session.execute(
            select(Artifact).offset(skip).limit(limit).order_by(Artifact.created_at.desc())
        )
        return list(result.scalars().all())

    async def update(self, artifact_id: UUID, data: ArtifactUpdate) -> Artifact | None:
        artifact = await self.get_by_id(artifact_id)
        if artifact is None:
            return None
        update_data = data.model_dump(exclude_unset=True)
        if "metadata" in update_data:
            artifact.metadata_ = update_data.pop("metadata")
        for field, value in update_data.items():
            setattr(artifact, field, value)
        await self._session.flush()
        await self._session.refresh(artifact)
        return artifact

    async def delete(self, artifact_id: UUID) -> bool:
        artifact = await self.get_by_id(artifact_id)
        if artifact is None:
            return False
        await self._session.delete(artifact)
        await self._session.flush()
        return True

    async def get_versions(self, artifact_id: UUID) -> list[ArtifactVersion]:
        result = await self._session.execute(
            select(ArtifactVersion)
            .where(ArtifactVersion.artifact_id == artifact_id)
            .order_by(ArtifactVersion.version_number.asc())
        )
        return list(result.scalars().all())

    async def get_latest_version(self, artifact_id: UUID) -> ArtifactVersion | None:
        result = await self._session.execute(
            select(ArtifactVersion)
            .where(ArtifactVersion.artifact_id == artifact_id)
            .order_by(ArtifactVersion.version_number.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
