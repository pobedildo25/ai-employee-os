from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.background_task import BackgroundTaskRecord
from app.task_queue.interfaces.queue import TaskQueueRepository
from app.task_queue.models import BackgroundTask, BackgroundTaskStatus


class InMemoryTaskQueueRepository(TaskQueueRepository):
    """In-process queue store — foundation without external brokers."""

    def __init__(self) -> None:
        self._tasks: dict[UUID, BackgroundTask] = {}

    async def save(self, task: BackgroundTask) -> BackgroundTask:
        self._tasks[task.id] = task
        return task

    async def get(self, task_id: UUID) -> BackgroundTask | None:
        return self._tasks.get(task_id)

    async def dequeue_next(self) -> BackgroundTask | None:
        queued = [
            task for task in self._tasks.values() if task.status == BackgroundTaskStatus.QUEUED
        ]
        if not queued:
            return None
        queued.sort(key=lambda task: (task.priority, task.created_at))
        task = queued[0]
        task.status = BackgroundTaskStatus.RUNNING
        task.started_at = datetime.now()
        self._tasks[task.id] = task
        return task

    async def list_by_status(
        self,
        statuses: list[BackgroundTaskStatus],
        *,
        limit: int = 100,
    ) -> list[BackgroundTask]:
        status_set = set(statuses)
        results = [task for task in self._tasks.values() if task.status in status_set]
        results.sort(key=lambda task: (task.priority, task.created_at))
        return results[:limit]


class PostgresTaskQueueRepository(TaskQueueRepository):
    """PostgreSQL-backed internal queue (no external broker)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, task: BackgroundTask) -> BackgroundTask:
        record = await self._session.get(BackgroundTaskRecord, task.id)
        if record is None:
            record = BackgroundTaskRecord(id=task.id, task_type=task.task_type)
            self._session.add(record)
        record.task_type = task.task_type
        record.status = task.status.value
        record.priority = task.priority
        record.payload = task.payload
        record.retry_count = task.retry_count
        record.created_at = task.created_at
        record.started_at = task.started_at
        record.finished_at = task.finished_at
        record.metadata_ = task.metadata
        record.error = task.error
        record.result = task.result
        await self._session.flush()
        return task

    async def get(self, task_id: UUID) -> BackgroundTask | None:
        record = await self._session.get(BackgroundTaskRecord, task_id)
        return _to_task(record) if record else None

    async def dequeue_next(self) -> BackgroundTask | None:
        stmt = (
            select(BackgroundTaskRecord)
            .where(BackgroundTaskRecord.status == BackgroundTaskStatus.QUEUED.value)
            .order_by(BackgroundTaskRecord.priority.asc(), BackgroundTaskRecord.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(stmt)
        record = result.scalar_one_or_none()
        if record is None:
            return None
        record.status = BackgroundTaskStatus.RUNNING.value
        record.started_at = datetime.now()
        await self._session.flush()
        return _to_task(record)

    async def list_by_status(
        self,
        statuses: list[BackgroundTaskStatus],
        *,
        limit: int = 100,
    ) -> list[BackgroundTask]:
        values = [status.value for status in statuses]
        stmt = (
            select(BackgroundTaskRecord)
            .where(BackgroundTaskRecord.status.in_(values))
            .order_by(BackgroundTaskRecord.priority.asc(), BackgroundTaskRecord.created_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [_to_task(record) for record in result.scalars().all()]


def _to_task(record: BackgroundTaskRecord) -> BackgroundTask:
    return BackgroundTask(
        id=record.id,
        task_type=record.task_type,
        status=BackgroundTaskStatus(record.status),
        priority=record.priority,
        payload=dict(record.payload or {}),
        retry_count=record.retry_count,
        created_at=record.created_at,
        started_at=record.started_at,
        finished_at=record.finished_at,
        metadata=dict(record.metadata_ or {}),
        error=record.error,
        result=dict(record.result) if record.result else None,
    )
