import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.task_queue.manager import TaskQueueManager
from app.task_queue.models import BackgroundTask

logger = logging.getLogger(__name__)

TaskHandler = Callable[[BackgroundTask], Awaitable[dict[str, Any] | None]]


class BackgroundWorker:
    """In-process worker architecture — no separate processes on this stage."""

    def __init__(
        self,
        queue_manager: TaskQueueManager,
        *,
        worker_id: str = "worker-1",
    ) -> None:
        self._queue = queue_manager
        self.worker_id = worker_id
        self._handlers: dict[str, TaskHandler] = {}

    def register(self, task_type: str, handler: TaskHandler) -> None:
        self._handlers[task_type] = handler

    def has_handler(self, task_type: str) -> bool:
        return task_type in self._handlers

    async def process(self, task: BackgroundTask) -> BackgroundTask:
        handler = self._handlers.get(task.task_type)
        if handler is None:
            return await self._queue.mark_failed(
                task.id,
                error=f"No handler registered for task_type={task.task_type}",
            )

        try:
            result = await handler(task)
            return await self._queue.mark_completed(task.id, result=result)
        except Exception as exc:
            logger.warning(
                "background worker failed | worker_id=%s task_id=%s error=%s",
                self.worker_id,
                task.id,
                exc,
            )
            failed = await self._queue.mark_failed(task.id, error=str(exc))
            if self._queue.retry_policy.should_retry(failed):
                return await self._queue.retry(failed.id)
            return failed

    async def process_next(self) -> BackgroundTask | None:
        """Dequeue one task and process it in-process. Architecture only — no daemon loop."""
        task = await self._queue.dequeue()
        if task is None:
            return None
        return await self.process(task)
