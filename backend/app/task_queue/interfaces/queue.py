from abc import ABC, abstractmethod
from uuid import UUID

from app.task_queue.models import BackgroundTask, BackgroundTaskStatus


class TaskQueueRepository(ABC):
    """Persistence contract for the internal task queue."""

    @abstractmethod
    async def save(self, task: BackgroundTask) -> BackgroundTask:
        raise NotImplementedError

    @abstractmethod
    async def get(self, task_id: UUID) -> BackgroundTask | None:
        raise NotImplementedError

    @abstractmethod
    async def dequeue_next(self) -> BackgroundTask | None:
        """Atomically pick the highest-priority QUEUED task and mark RUNNING."""
        raise NotImplementedError

    @abstractmethod
    async def list_by_status(
        self,
        statuses: list[BackgroundTaskStatus],
        *,
        limit: int = 100,
    ) -> list[BackgroundTask]:
        raise NotImplementedError
