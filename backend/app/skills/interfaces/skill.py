from abc import ABC, abstractmethod
from typing import Any

from app.skills.models import Capability, SkillMetadata


class Skill(ABC):
    """Base interface for system skills."""

    @abstractmethod
    def metadata(self) -> SkillMetadata:
        """Return skill metadata."""

    def name(self) -> str:
        return self.metadata().name

    def description(self) -> str:
        return self.metadata().description

    @abstractmethod
    def capabilities(self) -> list[Capability]:
        """Return capabilities provided by this skill."""

    @abstractmethod
    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute a task delegated to this skill."""
