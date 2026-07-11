from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.v1.dependencies import get_task_queue_manager, get_task_service
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate
from app.services.task_service import TaskService
from app.task_queue.manager import TaskQueueManager
from app.task_queue.models import BackgroundTask

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/background", response_model=list[BackgroundTask])
async def list_background_tasks(
    limit: int = Query(default=100, ge=1, le=500),
    queue: TaskQueueManager = Depends(get_task_queue_manager),
) -> list[BackgroundTask]:
    return await queue.list_active(limit=limit)


@router.get("", response_model=list[TaskRead])
async def list_tasks(
    project_id: UUID | None = Query(default=None),
    skip: int = 0,
    limit: int = 100,
    service: TaskService = Depends(get_task_service),
) -> list[TaskRead]:
    if project_id is not None:
        return await service.list_by_project(project_id, skip=skip, limit=limit)
    return await service.list_all(skip=skip, limit=limit)


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(
    data: TaskCreate,
    service: TaskService = Depends(get_task_service),
) -> TaskRead:
    return await service.create(data)


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(
    task_id: UUID,
    service: TaskService = Depends(get_task_service),
) -> TaskRead:
    task = await service.get_by_id(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.patch("/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: UUID,
    data: TaskUpdate,
    service: TaskService = Depends(get_task_service),
) -> TaskRead:
    task = await service.update(task_id, data)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: UUID,
    service: TaskService = Depends(get_task_service),
) -> None:
    deleted = await service.delete(task_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
