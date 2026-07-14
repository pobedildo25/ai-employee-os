from __future__ import annotations

import pytest

from app.adapters.telegram.mapper import TelegramMapper
from app.adapters.telegram.sender import InMemoryTelegramSender


def _update(message: dict) -> dict:
    return {"update_id": 1, "message": {"message_id": 10, "chat": {"id": 5}, "from": {"id": 7}, **message}}


def test_document_message_maps_with_media() -> None:
    mapper = TelegramMapper()
    request = mapper.map_update(
        _update(
            {
                "caption": "Проанализируй этот бриф",
                "document": {
                    "file_id": "DOC1",
                    "file_name": "brief.pdf",
                    "mime_type": "application/pdf",
                    "file_size": 1234,
                },
            }
        )
    )

    assert request is not None
    assert request.user_input == "Проанализируй этот бриф"
    assert len(request.media) == 1
    media = request.media[0]
    assert media.kind == "document"
    assert media.file_id == "DOC1"
    assert media.filename == "brief.pdf"
    assert request.context["has_media"] is True
    assert request.metadata["telegram_media"][0]["file_id"] == "DOC1"


def test_photo_message_takes_largest_and_synthesizes_goal() -> None:
    mapper = TelegramMapper()
    request = mapper.map_update(
        _update(
            {
                "photo": [
                    {"file_id": "SMALL", "width": 90, "height": 90},
                    {"file_id": "LARGE", "width": 1280, "height": 1280},
                ]
            }
        )
    )

    assert request is not None
    assert request.media[0].kind == "photo"
    assert request.media[0].file_id == "LARGE"
    assert request.user_input  # synthesized, non-empty


def test_voice_message_maps_and_defaults_goal() -> None:
    mapper = TelegramMapper()
    request = mapper.map_update(
        _update({"voice": {"file_id": "V1", "duration": 12, "mime_type": "audio/ogg"}})
    )

    assert request is not None
    assert request.media[0].kind == "voice"
    assert request.media[0].duration == 12
    assert "ауди" in request.user_input.lower()


def test_empty_message_returns_none() -> None:
    mapper = TelegramMapper()
    assert mapper.map_update(_update({})) is None


@pytest.mark.asyncio
async def test_inmemory_sender_download_roundtrip() -> None:
    sender = InMemoryTelegramSender()
    sender.downloads["F1"] = b"payload"

    assert await sender.download_file("F1") == b"payload"
    assert await sender.download_file("missing") is None
    assert sender.download_calls == ["F1", "missing"]
