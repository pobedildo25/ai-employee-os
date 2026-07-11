from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.v1.dependencies import get_project_service
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectRead])
async def list_projects(
    client_id: UUID | None = Query(default=None),
    skip: int = 0,
    limit: int = 100,
    service: ProjectService = Depends(get_project_service),
) -> list[ProjectRead]:
    if client_id is not None:
        return await service.list_by_client(client_id, skip=skip, limit=limit)
    return await service.list_all(skip=skip, limit=limit)


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    service: ProjectService = Depends(get_project_service),
) -> ProjectRead:
    return await service.create(data)


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: UUID,
    service: ProjectService = Depends(get_project_service),
) -> ProjectRead:
    project = await service.get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: UUID,
    data: ProjectUpdate,
    service: ProjectService = Depends(get_project_service),
) -> ProjectRead:
    project = await service.update(project_id, data)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    service: ProjectService = Depends(get_project_service),
) -> None:
    deleted = await service.delete(project_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
