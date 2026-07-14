from typing import Any

from pydantic import BaseModel, Field


class Capability(BaseModel):
    name: str
    description: str
    category: str
    # When False, Orchestrator may degrade a failed step without failing the task.
    # Declared by the Capability Registry / skill — never hard-coded by name elsewhere.
    critical: bool = True


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
