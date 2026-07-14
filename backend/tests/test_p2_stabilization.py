"""P2 stabilization — production readiness without new features."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from app.agents.executive.prompt import build_user_message
from app.clients.name_extractor import ExtractedSubject
from app.clients.resolver import CREATE_CLIENT_MIN_CONFIDENCE, BusinessClientResolver
from app.conversation.models import ConversationState, FlowMode
from app.conversation.requests import UserMessageRequest
from app.conversation.service import ConversationService


class _FakeRepo:
    def __init__(self) -> None:
        self.created: list[Any] = []
        self.by_name: dict[str, Any] = {}

    async def find_by_name(self, name: str):
        return self.by_name.get(name.casefold())

    async def create(self, data):
        client = type("C", (), {"id": uuid4(), "name": data.name})()
        self.created.append(data)
        self.by_name[data.name.casefold()] = client
        return client

    async def list_by_client(self, client_id, limit: int = 1):
        return []


@pytest.mark.asyncio
async def test_weak_extract_does_not_create_business_client(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _FakeRepo()

    async def fake_extract(*args, **kwargs):
        return ExtractedSubject(name="Амбигуоз", confidence=0.55)

    monkeypatch.setattr("app.clients.resolver.extract_business_subject", fake_extract)
    resolver = BusinessClientResolver(repo)
    assert CREATE_CLIENT_MIN_CONFIDENCE == 0.7
    result = await resolver.resolve("сделай что-нибудь для Амбигуоз")
    assert result is None
    assert repo.created == []


@pytest.mark.asyncio
async def test_strong_extract_creates_business_client(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _FakeRepo()

    async def fake_extract(*args, **kwargs):
        return ExtractedSubject(name="Яндекс", confidence=0.9)

    monkeypatch.setattr("app.clients.resolver.extract_business_subject", fake_extract)
    resolver = BusinessClientResolver(repo)
    result = await resolver.resolve("сделай КП для Яндекса")
    assert result is not None
    assert result.created is True
    assert len(repo.created) == 1


def test_executive_context_strips_learning_and_ast_blob() -> None:
    text = build_user_message(
        "Сделай короче",
        {
            "learning_context": [{"rule": "always research first"}],
            "learning_rules": [{"category": "strategy", "value": "x"}],
            "document_ast": {"huge": True},
            "has_prior_artifact": True,
            "dialog_continuity": {"flow_mode": "revision_prompted", "has_prior_artifact": True},
            "agency_context": {"agency_name": "NOVA"},
        },
    )
    assert "learning_context" not in text
    assert "always research first" not in text
    assert "has_document_ast" in text
    assert "huge" not in text
    assert "Dialog continuity" in text
    assert "revision_prompted" in text


def test_progress_only_for_create_plan() -> None:
    class Decision:
        def __init__(self, action: str, caps: list[str]):
            self.decision = type("D", (), {"action": type("A", (), {"value": action})()})()
            self.understanding = type("U", (), {"required_capabilities": caps, "goal": "КП"})()

    convo = ConversationState(user_id=1, chat_id=1)
    assert ConversationService._should_show_progress(Decision("CREATE_PLAN", ["research"]), convo)
    assert not ConversationService._should_show_progress(
        Decision("EXECUTE", ["strategy_analysis", "document_creation"]),
        convo,
    )


def test_runtime_payload_seeds_revision_continuity() -> None:
    service = ConversationService.__new__(ConversationService)
    convo = ConversationState(
        user_id=1,
        chat_id=1,
        flow_mode=FlowMode.REVISION_PROMPTED,
        artifact_ids=["art-1"],
        last_agent_state={
            "document_ast": {"root": {"type": "doc"}},
            "render_result": {"artifact_id": "art-1"},
        },
    )
    request = UserMessageRequest(text="Сократи первый раздел", user_id=1, chat_id=1)
    snapshot = {
        "client_id": str(uuid4()),
        "workspace_id": str(uuid4()),
        "active_session_id": "s1",
        "active_artifact_id": "art-1",
        "conversation": {"messages": []},
    }
    context, metadata = ConversationService._build_runtime_payload(
        service, request, snapshot, convo=convo
    )
    assert context["document_ast"]["root"]["type"] == "doc"
    assert context["user_feedback"] == "Сократи первый раздел"
    assert metadata["user_feedback"] == "Сократи первый раздел"
    assert context["source_artifact_id"] == "art-1"
    assert context["dialog_continuity"]["has_prior_artifact"] is True
