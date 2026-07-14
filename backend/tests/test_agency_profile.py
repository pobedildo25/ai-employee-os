from __future__ import annotations

import pytest

from app.agency.profile import AgencyProfile, build_agency_profile
from app.agents.executive.prompt import build_user_message
from app.context.models import ContextRequest
from app.context.providers.agency_provider import AgencyProfileProvider
from app.core.config import Settings
from app.document_creation.prompt import build_creation_user_message


def _settings(**kwargs) -> Settings:
    base = dict(
        openrouter_api_key="test-key",
        default_llm_model="mock-model",
    )
    base.update(kwargs)
    return Settings(**base)


def test_build_agency_profile_from_settings_splits_services() -> None:
    profile = build_agency_profile(
        _settings(
            agency_name="NOVA",
            agency_services="SMM, брендинг; перформанс\nдизайн",
            agency_tone="дружелюбно, по делу",
        )
    )
    assert profile.is_configured is True
    assert profile.services == ["SMM", "брендинг", "перформанс", "дизайн"]
    ctx = profile.to_context()
    assert ctx["name"] == "NOVA"
    assert ctx["tone_of_voice"] == "дружелюбно, по делу"


def test_build_agency_profile_json_override() -> None:
    profile = build_agency_profile(
        _settings(
            agency_name="NOVA",
            agency_profile_json='{"positioning": "перформанс-агентство", "inn": "7700000000"}',
        )
    )
    assert profile.positioning == "перформанс-агентство"
    # unknown keys land in extra and surface in context
    assert profile.to_context().get("inn") == "7700000000"


def test_unconfigured_profile_is_empty() -> None:
    profile = build_agency_profile(_settings(agency_name=""))
    assert profile.is_configured is False
    assert profile.to_context() == {}


@pytest.mark.asyncio
async def test_agency_provider_fetches_only_when_configured() -> None:
    configured = AgencyProfileProvider(AgencyProfile(name="NOVA", tone_of_voice="по делу"))
    empty = AgencyProfileProvider(AgencyProfile())
    req = ContextRequest(user_input="привет")

    assert (await configured.fetch(req))["agency_context"]["name"] == "NOVA"
    assert await empty.fetch(req) == {}


def test_executive_user_message_surfaces_agency() -> None:
    message = build_user_message(
        "сделай КП",
        context={"agency_context": {"name": "NOVA", "tone_of_voice": "по делу"}},
    )
    assert "Your agency" in message
    assert "NOVA" in message


def test_document_message_includes_agency_profile() -> None:
    message = build_creation_user_message(
        user_goal="сделай КП для Яндекса",
        context={},
        brand_profile=None,
        document_type="docx",
        requirements=[],
        capabilities=[],
        agency_profile={"name": "NOVA", "positioning": "перформанс"},
    )
    assert "Agency profile" in message
    assert "NOVA" in message
