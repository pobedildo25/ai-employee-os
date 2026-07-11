from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from app.task_queue.interfaces.queue import TaskQueueRepository
from app.task_queue.models import BackgroundTask, BackgroundTaskStatus
from app.task_queue.policies.retry_policy import RetryPolicy
from app.task_queue.repositories.task_queue_repository import InMemoryTaskQueueRepository


class TaskQueueManager:
    """Internal task queue manager — no Celery/RabbitMQ/Kafka/Redis Queue."""

    def __init__(
        self,
        repository: TaskQueueRepository | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self._repository = repository or InMemoryTaskQueueRepository()
        self._retry_policy = retry_policy or RetryPolicy()

    @property
    def retry_policy(self) -> RetryPolicy:
        return self._retry_policy

    async def enqueue(
        self,
        *,
        task_type: str,
        payload: dict[str, Any] | None = None,
        priority: int = 100,
        metadata: dict[str, Any] | None = None,
        task_id: UUID | None = None,
    ) -> BackgroundTask:
        task = BackgroundTask(
            id=task_id or uuid4(),
            task_type=task_type,
            status=BackgroundTaskStatus.QUEUED,
            priority=priority,
            payload=payload or {},
            metadata=metadata or {},
        )
        return await self._repository.save(task)

    async def dequeue(self) -> BackgroundTask | None:
        return await self._repository.dequeue_next()

    async def get(self, task_id: UUID) -> BackgroundTask | None:
        return await self._repository.get(task_id)

    async def cancel(self, task_id: UUID) -> BackgroundTask:
        task = await self._require(task_id)
        if task.status in {BackgroundTaskStatus.COMPLETED, BackgroundTaskStatus.CANCELLED}:
            return task
        task.status = BackgroundTaskStatus.CANCELLED
        task.finished_at = datetime.now()
        return await self._repository.save(task)

    async def retry(self, task_id: UUID) -> BackgroundTask:
        task = await self._require(task_id)
        if not self._retry_policy.should_retry(task):
            task.status = BackgroundTaskStatus.FAILED
            task.finished_at = datetime.now()
            task.error = task.error or "Retry limit exceeded"
            return await self._repository.save(task)

        task.retry_count = self._retry_policy.next_retry_count(task)
        task.status = BackgroundTaskStatus.QUEUED
        task.started_at = None
        task.finished_at = None
        task.error = None
        task.result = None
        return await self._repository.save(task)

    async def mark_completed(
        self,
        task_id: UUID,
        *,
        result: dict[str, Any] | None = None,
    ) -> BackgroundTask:
        task = await self._require(task_id)
        task.status = BackgroundTaskStatus.COMPLETED
        task.finished_at = datetime.now()
        task.result = result
        task.error = None
        return await self._repository.save(task)

    async def mark_failed(self, task_id: UUID, *, error: str) -> BackgroundTask:
        task = await self._require(task_id)
        task.status = BackgroundTaskStatus.FAILED
        task.finished_at = datetime.now()
        task.error = error
        return await self._repository.save(task)

    async def list_active(self, *, limit: int = 100) -> list[BackgroundTask]:
        return await self._repository.list_by_status(
            [BackgroundTaskStatus.QUEUED, BackgroundTaskStatus.RUNNING],
            limit=limit,
        )

    async def _require(self, task_id: UUID) -> BackgroundTask:
        task = await self._repository.get(task_id)
        if task is None:
            raise ValueError(f"Background task not found: {task_id}")
        return task
