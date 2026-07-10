from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ArtifactCreate(BaseModel):
    project_id: UUID
    client_id: UUID
    name: str = Field(min_length=1, max_length=255)
    artifact_type: str = Field(min_length=1, max_length=50)
    storage_path: str = Field(min_length=1, max_length=1024)
    version: int = Field(default=1, ge=1)


class ArtifactUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    artifact_type: str | None = Field(default=None, min_length=1, max_length=50)
    storage_path: str | None = Field(default=None, min_length=1, max_length=1024)
    version: int | None = Field(default=None, ge=1)


class ArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    client_id: UUID
    name: str
    artifact_type: str
    storage_path: str
    version: int
    created_at: datetime
    updated_at: datetime
