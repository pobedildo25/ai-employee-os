import logging

from app.core.config import Settings, get_settings
from app.skills.interfaces.skill import Skill
from app.skills.models import Capability

logger = logging.getLogger(__name__)


class CapabilityRegistryError(Exception):
    """Base registry error."""


class SkillAlreadyRegisteredError(CapabilityRegistryError):
    """Raised when registering a skill with a duplicate id."""


class CapabilityRegistry:
    """Registers skills and exposes searchable system capabilities."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._skills: dict[str, Skill] = {}
        self._capabilities: dict[str, Capability] = {}
        self._capability_to_skill: dict[str, str] = {}

    @property
    def enabled(self) -> bool:
        return self._settings.skills_enabled

    def register(self, skill: Skill) -> None:
        metadata = skill.metadata()
        if metadata.id in self._skills:
            raise SkillAlreadyRegisteredError(f"Skill already registered: {metadata.id}")

        self._skills[metadata.id] = skill
        for capability in skill.capabilities():
            self._capabilities[capability.name] = capability
            self._capability_to_skill[capability.name] = metadata.id

        logger.info(
            "skill registered | id=%s capabilities=%s enabled=%s",
            metadata.id,
            [capability.name for capability in skill.capabilities()],
            metadata.enabled,
        )

    def unregister(self, skill_id: str) -> bool:
        skill = self._skills.pop(skill_id, None)
        if skill is None:
            return False

        for capability in skill.capabilities():
            self._capabilities.pop(capability.name, None)
            self._capability_to_skill.pop(capability.name, None)

        logger.info("skill unregistered | id=%s", skill_id)
        return True

    def get_skill(self, skill_id: str) -> Skill | None:
        return self._skills.get(skill_id)

    def find_capabilities(self, names: str | list[str] | None = None) -> list[Capability]:
        if not self.enabled:
            return []

        if names is None:
            return self.list_available()

        query_names = [names] if isinstance(names, str) else names
        results: list[Capability] = []
        seen: set[str] = set()

        for name in query_names:
            capability = self._capabilities.get(name)
            if capability is None:
                continue
            skill = self._skills.get(self._capability_to_skill.get(name, ""))
            if skill is None or not skill.metadata().enabled:
                continue
            if capability.name in seen:
                continue
            seen.add(capability.name)
            results.append(capability)

        return results

    def get_skill_for_capability(self, capability_name: str) -> Skill | None:
        skill_id = self._capability_to_skill.get(capability_name)
        if skill_id is None:
            return None
        return self._skills.get(skill_id)

    def list_available(self) -> list[Capability]:
        if not self.enabled:
            return []

        results: list[Capability] = []
        for skill in self._skills.values():
            if not skill.metadata().enabled:
                continue
            results.extend(skill.capabilities())
        return results

    def list_available_for_prompt(self) -> list[dict[str, str]]:
        return [
            {"name": capability.name, "description": capability.description}
            for capability in self.list_available()
        ]


def create_capability_registry(settings: Settings | None = None) -> CapabilityRegistry:
    from app.skills.builtin.analysis_skill import AnalysisSkill
    from app.skills.builtin.brand_style_analysis_skill import BrandStyleAnalysisSkill
    from app.skills.builtin.document_analysis_skill import DocumentAnalysisSkill
    from app.skills.builtin.document_creation_skill import DocumentCreationSkill
    from app.skills.builtin.document_render_skill import DocumentRenderSkill
    from app.skills.builtin.document_skill import DocumentSkill
    from app.skills.builtin.file_skill import FileSkill

    settings = settings or get_settings()
    registry = CapabilityRegistry(settings)

    if settings.skills_enabled:
        registry.register(DocumentAnalysisSkill())
        registry.register(BrandStyleAnalysisSkill())
        registry.register(DocumentCreationSkill())
        registry.register(DocumentRenderSkill())
        registry.register(DocumentSkill())
        registry.register(AnalysisSkill())
        registry.register(FileSkill())

    return registry
