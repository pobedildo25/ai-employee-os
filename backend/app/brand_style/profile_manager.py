from typing import Any
from uuid import UUID

from app.brand_style.models import BrandProfile
from app.memory.models import MemoryItem, MemoryType


class BrandProfileNotFoundError(Exception):
    """Raised when a brand profile cannot be found."""


class BrandProfileManager:
    """In-memory brand profile store — foundation for memory-backed persistence."""

    def __init__(self) -> None:
        self._profiles: dict[UUID, BrandProfile] = {}
        self._client_index: dict[UUID, list[UUID]] = {}

    def create_profile(self, profile: BrandProfile) -> BrandProfile:
        self._profiles[profile.id] = profile
        if profile.client_id is not None:
            self._client_index.setdefault(profile.client_id, []).append(profile.id)
        return profile

    def get_profile(self, profile_id: UUID) -> BrandProfile | None:
        return self._profiles.get(profile_id)

    def get_profiles_for_client(self, client_id: UUID) -> list[BrandProfile]:
        profile_ids = self._client_index.get(client_id, [])
        return [self._profiles[profile_id] for profile_id in profile_ids if profile_id in self._profiles]

    def update_profile(self, profile_id: UUID, updates: dict[str, Any]) -> BrandProfile:
        profile = self._profiles.get(profile_id)
        if profile is None:
            raise BrandProfileNotFoundError(f"Brand profile not found: {profile_id}")

        updated = profile.model_copy(update=updates)
        self._profiles[profile_id] = updated
        return updated

    def compare_profiles(self, left_id: UUID, right_id: UUID) -> dict[str, Any]:
        left = self._profiles.get(left_id)
        right = self._profiles.get(right_id)
        if left is None or right is None:
            raise BrandProfileNotFoundError("One or both brand profiles were not found")

        return {
            "typography_match": left.typography == right.typography,
            "colors_match": left.colors == right.colors,
            "layout_match": left.layout_rules == right.layout_rules,
            "differences": {
                "typography": _diff_dict(left.typography, right.typography),
                "colors": _diff_dict(left.colors, right.colors),
                "layout_rules": _diff_dict(left.layout_rules, right.layout_rules),
            },
        }

    def to_memory_metadata(self, profile: BrandProfile) -> dict[str, Any]:
        return {
            "kind": "brand_profile",
            "profile_id": str(profile.id),
            "typography": profile.typography,
            "colors": profile.colors,
            "layout_rules": profile.layout_rules,
            "document_rules": profile.document_rules,
            "visual_elements": profile.visual_elements,
            "source_artifacts": [str(item) for item in profile.source_artifacts],
        }


def prepare_brand_memory_items(
    profile: BrandProfile,
    *,
    client_name: str | None = None,
    session_id: str | None = None,
) -> list[MemoryItem]:
    """Prepare memory candidates from a brand profile without auto-saving."""
    client_label = client_name or "Клиент"
    primary_color = profile.colors.get("primary", "не определён")
    heading_font = profile.typography.get("heading_font", "не определён")
    body_font = profile.typography.get("body_font", "не определён")

    return [
        MemoryItem(
            type=MemoryType.FACT,
            content=f"{client_label} использует корпоративный стиль документов",
            metadata={
                "kind": "brand_style_fact",
                "profile_id": str(profile.id),
                "client_id": str(profile.client_id) if profile.client_id else None,
            },
            importance=0.7,
            source="brand_style_engine",
            client_id=profile.client_id,
            session_id=session_id,
        ),
        MemoryItem(
            type=MemoryType.KNOWLEDGE,
            content=(
                f"Основной стиль документов {client_label}: "
                f"цвет {primary_color}, заголовки {heading_font}, текст {body_font}"
            ),
            metadata={
                "kind": "brand_profile",
                "profile_id": str(profile.id),
                "typography": profile.typography,
                "colors": profile.colors,
                "layout_rules": profile.layout_rules,
            },
            importance=0.8,
            source="brand_style_engine",
            client_id=profile.client_id,
            session_id=session_id,
        ),
    ]


def _diff_dict(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    keys = set(left) | set(right)
    differences: dict[str, Any] = {}
    for key in keys:
        if left.get(key) != right.get(key):
            differences[key] = {"left": left.get(key), "right": right.get(key)}
    return differences
