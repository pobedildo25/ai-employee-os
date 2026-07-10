from uuid import UUID

from app.repositories.task_repository import TaskRepository
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate


class TaskService:
    def __init__(self, repository: TaskRepository) -> None:
        self._repository = repository

    async def create(self, data: TaskCreate) -> TaskRead:
        task = await self._repository.create(data)
        return TaskRead.model_validate(task)

    async def get_by_id(self, task_id: UUID) -> TaskRead | None:
        task = await self._repository.get_by_id(task_id)
        return TaskRead.model_validate(task) if task else None

    async def list_by_project(self, project_id: UUID, skip: int = 0, limit: int = 100) -> list[TaskRead]:
        tasks = await self._repository.list_by_project(project_id, skip=skip, limit=limit)
        return [TaskRead.model_validate(task) for task in tasks]

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[TaskRead]:
        tasks = await self._repository.list_all(skip=skip, limit=limit)
        return [TaskRead.model_validate(task) for task in tasks]

    async def update(self, task_id: UUID, data: TaskUpdate) -> TaskRead | None:
        task = await self._repository.update(task_id, data)
        return TaskRead.model_validate(task) if task else None

    async def delete(self, task_id: UUID) -> bool:
        return await self._repository.delete(task_id)
