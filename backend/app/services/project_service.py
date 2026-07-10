from uuid import UUID

from app.repositories.project_repository import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate


class ProjectService:
    def __init__(self, repository: ProjectRepository) -> None:
        self._repository = repository

    async def create(self, data: ProjectCreate) -> ProjectRead:
        project = await self._repository.create(data)
        return ProjectRead.model_validate(project)

    async def get_by_id(self, project_id: UUID) -> ProjectRead | None:
        project = await self._repository.get_by_id(project_id)
        return ProjectRead.model_validate(project) if project else None

    async def list_by_client(self, client_id: UUID, skip: int = 0, limit: int = 100) -> list[ProjectRead]:
        projects = await self._repository.list_by_client(client_id, skip=skip, limit=limit)
        return [ProjectRead.model_validate(project) for project in projects]

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[ProjectRead]:
        projects = await self._repository.list_all(skip=skip, limit=limit)
        return [ProjectRead.model_validate(project) for project in projects]

    async def update(self, project_id: UUID, data: ProjectUpdate) -> ProjectRead | None:
        project = await self._repository.update(project_id, data)
        return ProjectRead.model_validate(project) if project else None

    async def delete(self, project_id: UUID) -> bool:
        return await self._repository.delete(project_id)
