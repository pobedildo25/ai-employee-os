from abc import ABC, abstractmethod
from uuid import UUID

from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectRepository(ABC):
    @abstractmethod
    async def create(self, data: ProjectCreate) -> Project:
        ...

    @abstractmethod
    async def get_by_id(self, project_id: UUID) -> Project | None:
        ...

    @abstractmethod
    async def list_by_client(self, client_id: UUID, skip: int = 0, limit: int = 100) -> list[Project]:
        ...

    @abstractmethod
    async def list_all(self, skip: int = 0, limit: int = 100) -> list[Project]:
        ...

    @abstractmethod
    async def update(self, project_id: UUID, data: ProjectUpdate) -> Project | None:
        ...

    @abstractmethod
    async def delete(self, project_id: UUID) -> bool:
        ...
