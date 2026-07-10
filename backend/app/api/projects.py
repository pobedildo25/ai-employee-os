from fastapi import APIRouter, status

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def list_projects() -> dict[str, str]:
    return {"detail": "Not implemented"}


@router.post("", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def create_project() -> dict[str, str]:
    return {"detail": "Not implemented"}


@router.get("/{project_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def get_project(project_id: str) -> dict[str, str]:
    return {"detail": "Not implemented"}


@router.patch("/{project_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def update_project(project_id: str) -> dict[str, str]:
    return {"detail": "Not implemented"}


@router.delete("/{project_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def delete_project(project_id: str) -> dict[str, str]:
    return {"detail": "Not implemented"}
