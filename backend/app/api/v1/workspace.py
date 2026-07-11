from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v1.dependencies import get_workspace_service
from app.schemas.workspace import WorkspaceOpenRequest, WorkspaceSnapshot
from app.workspace.service import WorkspaceService

router = APIRouter(prefix="/workspace", tags=["workspace"])


@router.post("/open", response_model=WorkspaceSnapshot, status_code=status.HTTP_201_CREATED)
async def open_workspace(
    data: WorkspaceOpenRequest,
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceSnapshot:
    snapshot = await service.open(
        client_id=data.client_id,
        project_id=data.project_id,
        task_id=data.task_id,
        artifact_id=data.artifact_id,
        metadata=data.metadata,
        open_session=data.open_session,
    )
    return WorkspaceSnapshot.model_validate(snapshot)


@router.get("/by-client/{client_id}", response_model=WorkspaceSnapshot)
async def get_workspace_by_client(
    client_id: UUID,
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceSnapshot:
    snapshot = await service.get_snapshot_for_client(client_id)
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return WorkspaceSnapshot.model_validate(snapshot)


@router.get("/{workspace_id}", response_model=WorkspaceSnapshot)
async def get_workspace(
    workspace_id: UUID,
    service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceSnapshot:
    snapshot = await service.get_snapshot(workspace_id)
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return WorkspaceSnapshot.model_validate(snapshot)
