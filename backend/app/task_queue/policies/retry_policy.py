from app.task_queue.models import BackgroundTask, BackgroundTaskStatus


class RetryPolicy:
    """Configurable retry limits — never infinite."""

    def __init__(self, max_retries: int = 3) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        self.max_retries = max_retries

    def should_retry(self, task: BackgroundTask) -> bool:
        if task.status == BackgroundTaskStatus.CANCELLED:
            return False
        return task.retry_count < self.max_retries

    def next_retry_count(self, task: BackgroundTask) -> int:
        return task.retry_count + 1

    def remaining_attempts(self, task: BackgroundTask) -> int:
        return max(0, self.max_retries - task.retry_count)
