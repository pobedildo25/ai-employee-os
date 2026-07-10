import pytest

from app.models.enums import ArtifactStatus
from app.schemas.artifact import ArtifactCreate, ArtifactNewVersionRequest, ArtifactUploadRequest


@pytest.mark.asyncio
async def test_create_artifact(artifact_service, ids) -> None:
    client_id, project_id = ids
    artifact = await artifact_service.create_artifact(
        ArtifactCreate(
            client_id=client_id,
            project_id=project_id,
            name="КП Яндекс",
            artifact_type="document",
            status=ArtifactStatus.DRAFT,
        )
    )
    assert artifact.name == "КП Яндекс"
    assert artifact.status == ArtifactStatus.DRAFT
    assert artifact.client_id == client_id


@pytest.mark.asyncio
async def test_upload_artifact_creates_version(artifact_service, ids) -> None:
    client_id, project_id = ids
    file_data = b"proposal content"

    artifact = await artifact_service.upload_artifact(
        ArtifactUploadRequest(
            client_id=client_id,
            project_id=project_id,
            name="КП Яндекс",
            artifact_type="document",
        ),
        file_data,
        "application/pdf",
    )

    assert artifact.status == ArtifactStatus.COMPLETED
    assert artifact.size == len(file_data)
    assert artifact.storage_path is not None

    history = await artifact_service.get_artifact_history(artifact.id)
    assert len(history) == 1
    assert history[0].version_number == 1


@pytest.mark.asyncio
async def test_create_new_version(artifact_service, ids) -> None:
    client_id, project_id = ids
    artifact = await artifact_service.upload_artifact(
        ArtifactUploadRequest(
            client_id=client_id,
            project_id=project_id,
            name="КП Яндекс",
            artifact_type="document",
        ),
        b"version 1",
        "text/plain",
    )

    version = await artifact_service.create_new_version(
        artifact.id,
        ArtifactNewVersionRequest(change_description="v2 update"),
        b"version 2 final",
        "text/plain",
    )

    assert version.version_number == 2
    history = await artifact_service.get_artifact_history(artifact.id)
    assert len(history) == 2
    assert history[-1].change_description == "v2 update"


@pytest.mark.asyncio
async def test_get_latest_version(artifact_service, ids) -> None:
    client_id, project_id = ids
    artifact = await artifact_service.upload_artifact(
        ArtifactUploadRequest(
            client_id=client_id,
            project_id=project_id,
            name="КП Яндекс",
            artifact_type="document",
        ),
        b"v1",
        "text/plain",
    )
    await artifact_service.create_new_version(
        artifact.id,
        ArtifactNewVersionRequest(change_description="v3_final"),
        b"v3",
        "text/plain",
    )

    latest = await artifact_service.get_latest_version(artifact.id)
    assert latest is not None
    assert latest.version_number == 2
