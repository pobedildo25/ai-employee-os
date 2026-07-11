import logging

from app.task_queue.manager import TaskQueueManager
from app.task_queue.models import BackgroundTask
from app.task_queue.worker import BackgroundWorker

logger = logging.getLogger(__name__)


class TaskScheduler:
    """Distributes queued tasks to workers. No cron — pull-based dispatch only."""

    def __init__(
        self,
        queue_manager: TaskQueueManager,
        workers: list[BackgroundWorker] | None = None,
    ) -> None:
        self._queue = queue_manager
        self._workers = list(workers or [])
        self._next_worker = 0

    def register_worker(self, worker: BackgroundWorker) -> None:
        self._workers.append(worker)

    @property
    def workers(self) -> list[BackgroundWorker]:
        return list(self._workers)

    def _select_worker(self, task: BackgroundTask) -> BackgroundWorker | None:
        if not self._workers:
            return None
        capable = [worker for worker in self._workers if worker.has_handler(task.task_type)]
        pool = capable or self._workers
        worker = pool[self._next_worker % len(pool)]
        self._next_worker += 1
        return worker

    async def dispatch_next(self) -> BackgroundTask | None:
        """Pull one queued task and assign it to a worker."""
        if not self._workers:
            logger.warning("scheduler has no workers registered")
            return None

        task = await self._queue.dequeue()
        if task is None:
            return None

        worker = self._select_worker(task)
        if worker is None:
            await self._queue.retry(task.id)
            return None

        logger.info(
            "scheduler dispatch | worker_id=%s task_id=%s task_type=%s",
            worker.worker_id,
            task.id,
            task.task_type,
        )
        return await worker.process(task)

    async def dispatch_batch(self, *, limit: int = 10) -> list[BackgroundTask]:
        processed: list[BackgroundTask] = []
        for _ in range(limit):
            result = await self.dispatch_next()
            if result is None:
                break
            processed.append(result)
        return processed
