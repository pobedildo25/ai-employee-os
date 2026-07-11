from uuid import uuid4

import pytest

from app.agent_runtime.state.models import create_initial_state
from app.task_queue.manager import TaskQueueManager
from app.task_queue.models import BackgroundTask, BackgroundTaskStatus
from app.task_queue.nodes.background_task_node import BackgroundTaskNode
from app.task_queue.policies.retry_policy import RetryPolicy
from app.task_queue.repositories.task_queue_repository import InMemoryTaskQueueRepository
from app.task_queue.scheduler import TaskScheduler
from app.task_queue.worker import BackgroundWorker
from app.workspace.manager import WorkspaceManager
from app.workspace.repositories.workspace_repository import InMemoryWorkspaceRepository


@pytest.fixture
def queue() -> TaskQueueManager:
    return TaskQueueManager(InMemoryTaskQueueRepository(), RetryPolicy(max_retries=2))


@pytest.mark.asyncio
async def test_background_task_model(queue: TaskQueueManager) -> None:
    task = await queue.enqueue(task_type="demo", payload={"x": 1}, priority=10)
    assert isinstance(task, BackgroundTask)
    assert task.status == BackgroundTaskStatus.QUEUED
    assert task.payload["x"] == 1
    assert task.retry_count == 0


@pytest.mark.asyncio
async def test_enqueue_dequeue(queue: TaskQueueManager) -> None:
    low = await queue.enqueue(task_type="low", priority=200)
    high = await queue.enqueue(task_type="high", priority=1)
    active = await queue.list_active()
    assert {item.id for item in active} == {low.id, high.id}

    first = await queue.dequeue()
    assert first is not None
    assert first.id == high.id
    assert first.status == BackgroundTaskStatus.RUNNING


@pytest.mark.asyncio
async def test_cancel(queue: TaskQueueManager) -> None:
    task = await queue.enqueue(task_type="cancel_me")
    cancelled = await queue.cancel(task.id)
    assert cancelled.status == BackgroundTaskStatus.CANCELLED
    assert cancelled.finished_at is not None
    assert await queue.dequeue() is None


@pytest.mark.asyncio
async def test_retry_policy_and_retry(queue: TaskQueueManager) -> None:
    policy = queue.retry_policy
    task = await queue.enqueue(task_type="flaky")
    await queue.dequeue()
    failed = await queue.mark_failed(task.id, error="boom")
    assert policy.should_retry(failed)

    retried = await queue.retry(failed.id)
    assert retried.status == BackgroundTaskStatus.QUEUED
    assert retried.retry_count == 1

    await queue.dequeue()
    failed_again = await queue.mark_failed(retried.id, error="boom2")
    retried_again = await queue.retry(failed_again.id)
    assert retried_again.retry_count == 2

    await queue.dequeue()
    exhausted = await queue.mark_failed(retried_again.id, error="boom3")
    final = await queue.retry(exhausted.id)
    assert final.status == BackgroundTaskStatus.FAILED
    assert final.retry_count == 2
    assert final.error == "boom3"
    assert not policy.should_retry(final)


@pytest.mark.asyncio
async def test_worker_process_next(queue: TaskQueueManager) -> None:
    worker = BackgroundWorker(queue, worker_id="w1")

    async def handle(task: BackgroundTask) -> dict:
        return {"echo": task.payload.get("value")}

    worker.register("echo", handle)
    await queue.enqueue(task_type="echo", payload={"value": 42})
    result = await worker.process_next()
    assert result is not None
    assert result.status == BackgroundTaskStatus.COMPLETED
    assert result.result == {"echo": 42}


@pytest.mark.asyncio
async def test_scheduler_dispatch(queue: TaskQueueManager) -> None:
    worker = BackgroundWorker(queue, worker_id="w-sched")

    async def handle(_task: BackgroundTask) -> dict:
        return {"ok": True}

    worker.register("job", handle)
    scheduler = TaskScheduler(queue, workers=[worker])
    await queue.enqueue(task_type="job", payload={})
    processed = await scheduler.dispatch_batch(limit=5)
    assert len(processed) == 1
    assert processed[0].status == BackgroundTaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_workspace_active_background_tasks(queue: TaskQueueManager) -> None:
    workspace_manager = WorkspaceManager(InMemoryWorkspaceRepository())
    client_id = uuid4()
    workspace = await workspace_manager.open_workspace(client_id)
    task = await queue.enqueue(task_type="migrate", payload={"client_id": str(client_id)})

    updated = await workspace_manager.track_background_task(workspace.id, task.id)
    assert task.id in updated.active_background_tasks
    assert await workspace_manager.get_active_background_tasks(updated) == [task.id]

    cleared = await workspace_manager.untrack_background_task(workspace.id, task.id)
    assert cleared.active_background_tasks == []


@pytest.mark.asyncio
async def test_background_task_node_with_workspace(queue: TaskQueueManager) -> None:
    workspace_manager = WorkspaceManager(InMemoryWorkspaceRepository())
    client_id = uuid4()
    workspace = await workspace_manager.open_workspace(client_id)
    node = BackgroundTaskNode(queue, workspace_manager)

    state = create_initial_state(
        execution_id="exec-bg-1",
        trace_id="trace-bg-1",
        user_input="Run background job",
        metadata={
            "background_task_type": "knowledge_migration",
            "background_task_payload": {"client_id": str(client_id)},
            "workspace_id": str(workspace.id),
        },
    )
    update = await node(state)
    assert update["status"] == "background_task_enqueued"
    assert update["background_task"]["task_type"] == "knowledge_migration"

    refreshed = await workspace_manager.get_workspace(workspace.id)
    assert refreshed is not None
    assert len(refreshed.active_background_tasks) == 1


@pytest.mark.asyncio
async def test_background_task_node_skips_without_type(queue: TaskQueueManager) -> None:
    node = BackgroundTaskNode(queue)
    state = create_initial_state(
        execution_id="exec-bg-2",
        trace_id="trace-bg-2",
        user_input="noop",
    )
    update = await node(state)
    assert update["status"] == "background_task_skipped"
    assert update["background_task"] is None
