from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.models.enums import ArtifactStatus


class ArtifactCreate(BaseModel):
    client_id: UUID
    project_id: UUID
    name: str = Field(min_length=1, max_length=255)
    artifact_type: str = Field(min_length=1, max_length=50)
    description: str | None = None
    status: ArtifactStatus = ArtifactStatus.DRAFT
    storage_path: str | None = None
    mime_type: str | None = None
    size: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] | None = None
    created_by: str | None = None


class ArtifactUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    artifact_type: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = None
    status: ArtifactStatus | None = None
    storage_path: str | None = None
    mime_type: str | None = None
    size: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] | None = None
    created_by: str | None = None


class ArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: UUID
    project_id: UUID
    name: str
    artifact_type: str
    description: str | None
    status: ArtifactStatus
    storage_path: str | None
    mime_type: str | None
    size: int | None
    metadata: dict[str, Any] | None = Field(validation_alias="metadata_")
    created_by: str | None
    created_at: datetime
    updated_at: datetime

    @field_serializer("metadata")
    def serialize_metadata(self, value: dict[str, Any] | None, _info: object) -> dict[str, Any] | None:
        return value


class ArtifactVersionCreate(BaseModel):
    storage_path: str = Field(min_length=1, max_length=1024)
    metadata: dict[str, Any] | None = None
    created_by: str | None = None
    change_description: str | None = None


class ArtifactVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    artifact_id: UUID
    version_number: int
    storage_path: str
    metadata: dict[str, Any] | None = Field(validation_alias="metadata_")
    created_at: datetime
    created_by: str | None
    change_description: str | None

    @field_serializer("metadata")
    def serialize_metadata(self, value: dict[str, Any] | None, _info: object) -> dict[str, Any] | None:
        return value


class ArtifactUploadRequest(BaseModel):
    client_id: UUID
    project_id: UUID
    name: str = Field(min_length=1, max_length=255)
    artifact_type: str = Field(min_length=1, max_length=50)
    description: str | None = None
    created_by: str | None = None
    metadata: dict[str, Any] | None = None


class ArtifactNewVersionRequest(BaseModel):
    change_description: str | None = None
    created_by: str | None = None
    metadata: dict[str, Any] | None = None
