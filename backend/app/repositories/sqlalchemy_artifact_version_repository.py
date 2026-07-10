from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact_version import ArtifactVersion
from app.repositories.artifact_version_repository import ArtifactVersionRepository
from app.schemas.artifact import ArtifactVersionCreate


class SQLAlchemyArtifactVersionRepository(ArtifactVersionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_version(
        self,
        artifact_id: UUID,
        version_number: int,
        data: ArtifactVersionCreate,
    ) -> ArtifactVersion:
        version = ArtifactVersion(
            artifact_id=artifact_id,
            version_number=version_number,
            storage_path=data.storage_path,
            metadata_=data.metadata,
            created_by=data.created_by,
            change_description=data.change_description,
        )
        self._session.add(version)
        await self._session.flush()
        await self._session.refresh(version)
        return version

    async def get_history(self, artifact_id: UUID) -> list[ArtifactVersion]:
        result = await self._session.execute(
            select(ArtifactVersion)
            .where(ArtifactVersion.artifact_id == artifact_id)
            .order_by(ArtifactVersion.version_number.asc())
        )
        return list(result.scalars().all())

    async def get_by_version_number(self, artifact_id: UUID, version_number: int) -> ArtifactVersion | None:
        result = await self._session.execute(
            select(ArtifactVersion).where(
                ArtifactVersion.artifact_id == artifact_id,
                ArtifactVersion.version_number == version_number,
            )
        )
        return result.scalar_one_or_none()
