import json
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status

from app.api.v1.dependencies import get_artifact_service, get_project_service
from app.schemas.artifact import (
    ArtifactCreate,
    ArtifactNewVersionRequest,
    ArtifactRead,
    ArtifactUploadRequest,
    ArtifactVersionRead,
)
from app.security.models import SecurityPrincipal
from app.security.tenant import enforce_client_access, scoped_client_id
from app.services.artifact_service import ArtifactService
from app.services.project_service import ProjectService

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


def _principal(request: Request) -> SecurityPrincipal | None:
    return getattr(request.state, "principal", None)


@router.get("", response_model=list[ArtifactRead])
async def list_artifacts(
    request: Request,
    project_id: UUID | None = Query(default=None),
    skip: int = 0,
    limit: int = 100,
    service: ArtifactService = Depends(get_artifact_service),
    project_service: ProjectService = Depends(get_project_service),
) -> list[ArtifactRead]:
    principal = _principal(request)
    scoped = scoped_client_id(principal)

    if project_id is not None:
        project = await project_service.get_by_id(project_id)
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        enforce_client_access(principal, project.client_id)
        return await service.list_by_project(project_id, skip=skip, limit=limit)

    if scoped is not None:
        return await service.list_by_client(scoped, skip=skip, limit=limit)
    return await service.list_all(skip=skip, limit=limit)


@router.post("", response_model=ArtifactRead, status_code=status.HTTP_201_CREATED)
async def create_artifact(
    request: Request,
    client_id: UUID = Form(...),
    project_id: UUID = Form(...),
    name: str = Form(...),
    artifact_type: str = Form(...),
    description: str | None = Form(None),
    created_by: str | None = Form(None),
    metadata: str | None = Form(None),
    file: UploadFile | None = File(None),
    service: ArtifactService = Depends(get_artifact_service),
) -> ArtifactRead:
    enforce_client_access(_principal(request), client_id)
    parsed_metadata = json.loads(metadata) if metadata else None

    if file is not None:
        file_data = await file.read()
        upload_request = ArtifactUploadRequest(
            client_id=client_id,
            project_id=project_id,
            name=name,
            artifact_type=artifact_type,
            description=description,
            created_by=created_by,
            metadata=parsed_metadata,
        )
        return await service.upload_artifact(upload_request, file_data, file.content_type)

    artifact_data = ArtifactCreate(
        client_id=client_id,
        project_id=project_id,
        name=name,
        artifact_type=artifact_type,
        description=description,
        created_by=created_by,
        metadata=parsed_metadata,
    )
    return await service.create_artifact(artifact_data)


@router.get("/{artifact_id}", response_model=ArtifactRead)
async def get_artifact(
    request: Request,
    artifact_id: UUID,
    service: ArtifactService = Depends(get_artifact_service),
) -> ArtifactRead:
    artifact = await service.get_by_id(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    enforce_client_access(_principal(request), artifact.client_id)
    return artifact


@router.get("/{artifact_id}/versions", response_model=list[ArtifactVersionRead])
async def get_artifact_versions(
    request: Request,
    artifact_id: UUID,
    service: ArtifactService = Depends(get_artifact_service),
) -> list[ArtifactVersionRead]:
    artifact = await service.get_by_id(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    enforce_client_access(_principal(request), artifact.client_id)
    return await service.get_artifact_history(artifact_id)


@router.post(
    "/{artifact_id}/versions",
    response_model=ArtifactVersionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_artifact_version(
    request: Request,
    artifact_id: UUID,
    file: UploadFile = File(...),
    change_description: str | None = Form(None),
    created_by: str | None = Form(None),
    metadata: str | None = Form(None),
    service: ArtifactService = Depends(get_artifact_service),
) -> ArtifactVersionRead:
    artifact = await service.get_by_id(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    enforce_client_access(_principal(request), artifact.client_id)

    file_data = await file.read()
    version_request = ArtifactNewVersionRequest(
        change_description=change_description,
        created_by=created_by,
        metadata=json.loads(metadata) if metadata else None,
    )
    try:
        return await service.create_new_version(artifact_id, version_request, file_data, file.content_type)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{artifact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_artifact(
    request: Request,
    artifact_id: UUID,
    service: ArtifactService = Depends(get_artifact_service),
) -> None:
    artifact = await service.get_by_id(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    enforce_client_access(_principal(request), artifact.client_id)
    deleted = await service.delete(artifact_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
