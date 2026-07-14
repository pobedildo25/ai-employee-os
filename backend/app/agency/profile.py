"""The agency's own identity — "who WE are".

Distinct from ``BrandProfile`` (which is a *client's* visual styling). This
profile answers "which agency does the assistant work for" and is injected into
every dialogue and every generated document, so proposals are authored FROM our
agency's perspective (first person "мы") with our tone, positioning and
requisites — never as some anonymous third party.

Configured via environment (``AGENCY_*`` settings) with an optional full-JSON
override (``AGENCY_PROFILE_JSON``). Everything is overridable so the user can
drop in the real agency details (and later a branded Word template).
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache

from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class AgencyProfile(BaseModel):
    name: str = ""
    tagline: str = ""
    positioning: str = ""
    services: list[str] = Field(default_factory=list)
    tone_of_voice: str = ""
    requisites: str = ""
    contacts: str = ""
    website: str = ""
    extra: dict[str, str] = Field(default_factory=dict)

    @property
    def is_configured(self) -> bool:
        return bool(self.name.strip())

    def to_context(self) -> dict[str, object]:
        """Compact, non-empty representation for prompts and context injection."""
        data: dict[str, object] = {}
        if self.name.strip():
            data["name"] = self.name.strip()
        if self.tagline.strip():
            data["tagline"] = self.tagline.strip()
        if self.positioning.strip():
            data["positioning"] = self.positioning.strip()
        if self.services:
            data["services"] = self.services
        if self.tone_of_voice.strip():
            data["tone_of_voice"] = self.tone_of_voice.strip()
        if self.requisites.strip():
            data["requisites"] = self.requisites.strip()
        if self.contacts.strip():
            data["contacts"] = self.contacts.strip()
        if self.website.strip():
            data["website"] = self.website.strip()
        for key, value in self.extra.items():
            if str(value).strip():
                data[key] = value
        return data

    def to_prompt_block(self) -> str:
        """Human-readable block for system prompts."""
        lines = [f"Agency name: {self.name}"]
        if self.tagline.strip():
            lines.append(f"Tagline: {self.tagline}")
        if self.positioning.strip():
            lines.append(f"Positioning: {self.positioning}")
        if self.services:
            lines.append(f"Services: {', '.join(self.services)}")
        if self.tone_of_voice.strip():
            lines.append(f"Tone of voice: {self.tone_of_voice}")
        if self.requisites.strip():
            lines.append(f"Requisites: {self.requisites}")
        if self.contacts.strip():
            lines.append(f"Contacts: {self.contacts}")
        if self.website.strip():
            lines.append(f"Website: {self.website}")
        return "\n".join(lines)


def _split_services(raw: str) -> list[str]:
    if not raw:
        return []
    parts = raw.replace(";", "\n").replace(",", "\n").splitlines()
    return [p.strip() for p in parts if p.strip()]


def build_agency_profile(settings: Settings | None = None) -> AgencyProfile:
    settings = settings or get_settings()
    profile = AgencyProfile(
        name=getattr(settings, "agency_name", "") or "",
        tagline=getattr(settings, "agency_tagline", "") or "",
        positioning=getattr(settings, "agency_positioning", "") or "",
        services=_split_services(getattr(settings, "agency_services", "") or ""),
        tone_of_voice=getattr(settings, "agency_tone", "") or "",
        requisites=getattr(settings, "agency_requisites", "") or "",
        contacts=getattr(settings, "agency_contacts", "") or "",
        website=getattr(settings, "agency_website", "") or "",
    )

    override_raw = getattr(settings, "agency_profile_json", "") or ""
    if override_raw.strip():
        try:
            override = json.loads(override_raw)
            if isinstance(override, dict):
                profile = profile.model_copy(update=_normalize_override(override))
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("invalid AGENCY_PROFILE_JSON, ignoring | error=%s", exc)

    return profile


def _normalize_override(override: dict) -> dict:
    update: dict[str, object] = {}
    known = set(AgencyProfile.model_fields.keys())
    extra: dict[str, str] = {}
    for key, value in override.items():
        if key == "services" and isinstance(value, str):
            update["services"] = _split_services(value)
        elif key in known:
            update[key] = value
        else:
            extra[key] = str(value)
    if extra:
        update["extra"] = {**update.get("extra", {}), **extra}  # type: ignore[dict-item]
    return update


@lru_cache
def get_agency_profile() -> AgencyProfile:
    return build_agency_profile()
