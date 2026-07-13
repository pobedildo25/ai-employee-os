import pytest

from app.core.config import Settings
from app.core.feature_guards import OptionalStackMisconfigured, validate_optional_stacks
from app.memory.semantic.qdrant_memory import create_semantic_memory
from app.skills.registry import create_capability_registry


def test_validate_optional_stacks_ok_when_flags_off() -> None:
    validate_optional_stacks(Settings(research_enabled=False, semantic_memory_enabled=False))


def test_research_enabled_without_backend_fails() -> None:
    with pytest.raises(OptionalStackMisconfigured, match="research_enabled"):
        validate_optional_stacks(Settings(research_enabled=True, research_allow_mock=False))


def test_research_enabled_sonar_with_key_ok() -> None:
    validate_optional_stacks(
        Settings(
            research_enabled=True,
            research_provider="sonar",
            openrouter_api_key="sk-or-v1-aaaaaaaaaaaaaaaaaaaaaaaa",
        )
    )


def test_semantic_enabled_without_allow_stub_fails() -> None:
    with pytest.raises(OptionalStackMisconfigured, match="semantic_memory"):
        validate_optional_stacks(Settings(semantic_memory_enabled=True, embedding_allow_stub=False))


def test_registry_refuses_research_without_allow_mock() -> None:
    with pytest.raises(OptionalStackMisconfigured):
        create_capability_registry(Settings(skills_enabled=True, research_enabled=True))


def test_create_semantic_memory_refuses_stub_without_allow() -> None:
    with pytest.raises(OptionalStackMisconfigured):
        create_semantic_memory(Settings(semantic_memory_enabled=True, embedding_allow_stub=False))


def test_escape_hatches_allow_test_enable() -> None:
    validate_optional_stacks(
        Settings(
            research_enabled=True,
            research_allow_mock=True,
            semantic_memory_enabled=True,
            embedding_allow_stub=True,
        )
    )
    registry = create_capability_registry(
        Settings(skills_enabled=True, research_enabled=True, research_allow_mock=True)
    )
    assert registry.get_skill("research_skill") is not None
