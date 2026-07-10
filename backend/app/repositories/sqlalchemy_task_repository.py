from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.repositories.task_repository import TaskRepository
from app.schemas.task import TaskCreate, TaskUpdate


class SQLAlchemyTaskRepository(TaskRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: TaskCreate) -> Task:
        task = Task(
            project_id=data.project_id,
            title=data.title,
            description=data.description,
            status=data.status,
        )
        self._session.add(task)
        await self._session.flush()
        await self._session.refresh(task)
        return task

    async def get_by_id(self, task_id: UUID) -> Task | None:
        return await self._session.get(Task, task_id)

    async def list_by_project(self, project_id: UUID, skip: int = 0, limit: int = 100) -> list[Task]:
        result = await self._session.execute(
            select(Task)
            .where(Task.project_id == project_id)
            .offset(skip)
            .limit(limit)
            .order_by(Task.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[Task]:
        result = await self._session.execute(
            select(Task).offset(skip).limit(limit).order_by(Task.created_at.desc())
        )
        return list(result.scalars().all())

    async def update(self, task_id: UUID, data: TaskUpdate) -> Task | None:
        task = await self.get_by_id(task_id)
        if task is None:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(task, field, value)
        await self._session.flush()
        await self._session.refresh(task)
        return task

    async def delete(self, task_id: UUID) -> bool:
        task = await self.get_by_id(task_id)
        if task is None:
            return False
        await self._session.delete(task)
        await self._session.flush()
        return True
