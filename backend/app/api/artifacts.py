import json
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.api.deps import get_artifact_service
from app.schemas.artifact import (
    ArtifactCreate,
    ArtifactNewVersionRequest,
    ArtifactRead,
    ArtifactUploadRequest,
    ArtifactVersionRead,
)
from app.services.artifact_service import ArtifactService

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


@router.post("", response_model=ArtifactRead, status_code=status.HTTP_201_CREATED)
async def create_artifact(
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
    parsed_metadata = json.loads(metadata) if metadata else None

    if file is not None:
        file_data = await file.read()
        request = ArtifactUploadRequest(
            client_id=client_id,
            project_id=project_id,
            name=name,
            artifact_type=artifact_type,
            description=description,
            created_by=created_by,
            metadata=parsed_metadata,
        )
        return await service.upload_artifact(request, file_data, file.content_type)

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
    artifact_id: UUID,
    service: ArtifactService = Depends(get_artifact_service),
) -> ArtifactRead:
    artifact = await service.get_by_id(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    return artifact


@router.get("/{artifact_id}/versions", response_model=list[ArtifactVersionRead])
async def get_artifact_versions(
    artifact_id: UUID,
    service: ArtifactService = Depends(get_artifact_service),
) -> list[ArtifactVersionRead]:
    artifact = await service.get_by_id(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    return await service.get_artifact_history(artifact_id)


@router.post("/{artifact_id}/versions", response_model=ArtifactVersionRead, status_code=status.HTTP_201_CREATED)
async def create_artifact_version(
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

    file_data = await file.read()
    request = ArtifactNewVersionRequest(
        change_description=change_description,
        created_by=created_by,
        metadata=json.loads(metadata) if metadata else None,
    )
    try:
        return await service.create_new_version(artifact_id, request, file_data, file.content_type)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
