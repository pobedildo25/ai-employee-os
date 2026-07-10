from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate


class SQLAlchemyProjectRepository(ProjectRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: ProjectCreate) -> Project:
        project = Project(
            client_id=data.client_id,
            name=data.name,
            description=data.description,
            status=data.status,
        )
        self._session.add(project)
        await self._session.flush()
        await self._session.refresh(project)
        return project

    async def get_by_id(self, project_id: UUID) -> Project | None:
        return await self._session.get(Project, project_id)

    async def list_by_client(self, client_id: UUID, skip: int = 0, limit: int = 100) -> list[Project]:
        result = await self._session.execute(
            select(Project)
            .where(Project.client_id == client_id)
            .offset(skip)
            .limit(limit)
            .order_by(Project.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[Project]:
        result = await self._session.execute(
            select(Project).offset(skip).limit(limit).order_by(Project.created_at.desc())
        )
        return list(result.scalars().all())

    async def update(self, project_id: UUID, data: ProjectUpdate) -> Project | None:
        project = await self.get_by_id(project_id)
        if project is None:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(project, field, value)
        await self._session.flush()
        await self._session.refresh(project)
        return project

    async def delete(self, project_id: UUID) -> bool:
        project = await self.get_by_id(project_id)
        if project is None:
            return False
        await self._session.delete(project)
        await self._session.flush()
        return True
