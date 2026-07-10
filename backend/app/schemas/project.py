from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    client_id: UUID
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    status: str = Field(default="active", max_length=50)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = Field(default=None, max_length=50)


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: UUID
    name: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime
