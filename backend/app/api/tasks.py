from fastapi import APIRouter, status

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def list_tasks() -> dict[str, str]:
    return {"detail": "Not implemented"}


@router.post("", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def create_task() -> dict[str, str]:
    return {"detail": "Not implemented"}


@router.get("/{task_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def get_task(task_id: str) -> dict[str, str]:
    return {"detail": "Not implemented"}


@router.patch("/{task_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def update_task(task_id: str) -> dict[str, str]:
    return {"detail": "Not implemented"}


@router.delete("/{task_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def delete_task(task_id: str) -> dict[str, str]:
    return {"detail": "Not implemented"}
