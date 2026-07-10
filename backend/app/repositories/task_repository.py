from abc import ABC, abstractmethod
from uuid import UUID

from app.models.task import Task
from app.schemas.task import TaskCreate, TaskUpdate


class TaskRepository(ABC):
    @abstractmethod
    async def create(self, data: TaskCreate) -> Task:
        ...

    @abstractmethod
    async def get_by_id(self, task_id: UUID) -> Task | None:
        ...

    @abstractmethod
    async def list_by_project(self, project_id: UUID, skip: int = 0, limit: int = 100) -> list[Task]:
        ...

    @abstractmethod
    async def list_all(self, skip: int = 0, limit: int = 100) -> list[Task]:
        ...

    @abstractmethod
    async def update(self, task_id: UUID, data: TaskUpdate) -> Task | None:
        ...

    @abstractmethod
    async def delete(self, task_id: UUID) -> bool:
        ...
