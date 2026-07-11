from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v1.dependencies import get_artifact_service, get_file_processing_service
from app.schemas.artifact import ArtifactRead
from app.services.artifact_service import ArtifactService
from app.services.file_processing_service import FileProcessingService

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/{artifact_id}/process", response_model=ArtifactRead)
async def process_document(
    artifact_id: UUID,
    artifact_service: ArtifactService = Depends(get_artifact_service),
    file_service: FileProcessingService = Depends(get_file_processing_service),
) -> ArtifactRead:
    artifact = await artifact_service.get_by_id(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    try:
        return await file_service.process_artifact(artifact_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
