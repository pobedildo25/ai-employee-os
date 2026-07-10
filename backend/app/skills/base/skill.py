from typing import Any

from app.skills.interfaces.skill import Skill
from app.skills.models import Capability, SkillMetadata


class BaseSkill(Skill):
    """Base skill with stub execution — no business logic."""

    def __init__(self, metadata: SkillMetadata, capabilities: list[Capability]) -> None:
        self._metadata = metadata
        self._capabilities = capabilities

    def metadata(self) -> SkillMetadata:
        return self._metadata

    def capabilities(self) -> list[Capability]:
        return list(self._capabilities)

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "not_implemented",
            "skill": self.name(),
            "message": "Skill execution is not available at this stage",
            "payload_keys": list(payload.keys()),
        }
