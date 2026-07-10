from typing import Any

from pydantic import BaseModel, Field


class Capability(BaseModel):
    name: str
    description: str
    category: str


class SkillMetadata(BaseModel):
    id: str
    name: str
    description: str
    capabilities: list[str] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    version: str = "1.0.0"
    enabled: bool = True


class RequiredCapabilities(BaseModel):
    requested: list[str] = Field(default_factory=list)
    resolved: list[Capability] = Field(default_factory=list)
    unknown: list[str] = Field(default_factory=list)
