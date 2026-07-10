from fastapi import APIRouter, status

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


@router.get("", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def list_artifacts() -> dict[str, str]:
    return {"detail": "Not implemented"}


@router.post("", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def create_artifact() -> dict[str, str]:
    return {"detail": "Not implemented"}


@router.get("/{artifact_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def get_artifact(artifact_id: str) -> dict[str, str]:
    return {"detail": "Not implemented"}


@router.patch("/{artifact_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def update_artifact(artifact_id: str) -> dict[str, str]:
    return {"detail": "Not implemented"}


@router.delete("/{artifact_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def delete_artifact(artifact_id: str) -> dict[str, str]:
    return {"detail": "Not implemented"}
