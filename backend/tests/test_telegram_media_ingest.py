from __future__ import annotations

import pytest

from app.adapters.telegram.media import MediaIngestor
from app.adapters.telegram.models import InboundMedia
from app.adapters.telegram.sender import InMemoryTelegramSender
from app.core.config import Settings
from app.file_processing.models import ExtractedContent


class FakeFileProcessor:
    def __init__(self, text: str = "Extracted brief text") -> None:
        self._text = text
        self.calls: list[str] = []

    def process_bytes(self, data: bytes, filename: str, mime_type: str | None = None) -> ExtractedContent:
        self.calls.append(filename)
        return ExtractedContent(text=self._text, pages=2)


class FakeVisionGateway:
    def __init__(self, description: str = "На фото — логотип бренда") -> None:
        self._description = description
        self.calls: list[str] = []

    async def vision(self, prompt, images, **kwargs):  # noqa: ANN001
        self.calls.append(prompt)
        return self._description


class FakeTranscriber:
    def __init__(self, transcript: str | None) -> None:
        self._transcript = transcript

    async def transcribe(self, data, **kwargs):  # noqa: ANN001
        return self._transcript


def _settings(**overrides) -> Settings:
    base = dict(openrouter_api_key="k", vision_enabled=True, attachment_max_chars=5000)
    base.update(overrides)
    return Settings(**base)


@pytest.mark.asyncio
async def test_ingest_document_extracts_text() -> None:
    sender = InMemoryTelegramSender()
    sender.downloads["DOC"] = b"%PDF-fake"
    ingestor = MediaIngestor(
        sender,
        file_processor=FakeFileProcessor("Brief: launch campaign"),
        transcriber=FakeTranscriber(None),
        settings=_settings(),
    )

    result = await ingestor.ingest(
        [InboundMedia(kind="document", file_id="DOC", filename="brief.pdf", mime_type="application/pdf")],
        user_input="Проанализируй бриф",
    )

    assert result.processed is True
    assert result.context["attached_documents"][0]["text"] == "Brief: launch campaign"
    assert result.context["attached_documents"][0]["title"] == "brief.pdf"


@pytest.mark.asyncio
async def test_ingest_image_uses_vision() -> None:
    sender = InMemoryTelegramSender()
    sender.downloads["IMG"] = b"\xff\xd8\xff"
    vision = FakeVisionGateway("Синий логотип на белом фоне")
    ingestor = MediaIngestor(
        sender,
        file_processor=FakeFileProcessor(),
        gateway=vision,
        transcriber=FakeTranscriber(None),
        settings=_settings(),
    )

    result = await ingestor.ingest(
        [InboundMedia(kind="photo", file_id="IMG", mime_type="image/jpeg")],
        user_input="Что на картинке?",
    )

    assert vision.calls == ["Что на картинке?"]
    assert result.context["attached_images"][0]["description"] == "Синий логотип на белом фоне"


@pytest.mark.asyncio
async def test_ingest_audio_transcribes() -> None:
    sender = InMemoryTelegramSender()
    sender.downloads["V"] = b"OggS-fake"
    ingestor = MediaIngestor(
        sender,
        file_processor=FakeFileProcessor(),
        transcriber=FakeTranscriber("Клиент попросил КП до пятницы"),
        settings=_settings(),
    )

    result = await ingestor.ingest(
        [InboundMedia(kind="voice", file_id="V", mime_type="audio/ogg", duration=15)],
        user_input="Расшифруй",
    )

    assert result.context["attached_transcripts"][0]["transcript"] == "Клиент попросил КП до пятницы"


@pytest.mark.asyncio
async def test_ingest_audio_without_transcription_notes_gracefully() -> None:
    sender = InMemoryTelegramSender()
    sender.downloads["V"] = b"OggS-fake"
    ingestor = MediaIngestor(
        sender,
        file_processor=FakeFileProcessor(),
        transcriber=FakeTranscriber(None),
        settings=_settings(),
    )

    result = await ingestor.ingest(
        [InboundMedia(kind="voice", file_id="V", mime_type="audio/ogg")],
        user_input="Расшифруй",
    )

    assert "attached_transcripts" not in result.context
    assert any("расшифровка" in note.lower() for note in result.notes)


@pytest.mark.asyncio
async def test_flow_ingest_media_folds_into_context_and_metadata() -> None:
    from app.adapters.telegram.flow import TelegramProductFlow
    from app.adapters.telegram.models import TelegramExecutionRequest

    sender = InMemoryTelegramSender()
    sender.downloads["DOC"] = b"%PDF-fake"
    ingestor = MediaIngestor(
        sender,
        file_processor=FakeFileProcessor("Бриф: запуск кампании"),
        transcriber=FakeTranscriber(None),
        settings=_settings(),
    )
    flow = TelegramProductFlow(
        runtime=None,
        session_manager=None,
        sender=sender,
        conversation_store=None,
        media_ingestor=ingestor,
    )
    request = TelegramExecutionRequest(
        user_input="Сделай КП по этому брифу",
        telegram_user_id=1,
        telegram_chat_id=2,
        media=[InboundMedia(kind="document", file_id="DOC", filename="brief.pdf", mime_type="application/pdf")],
    )

    await flow._ingest_media(request)

    assert request.context["attached_documents"][0]["text"] == "Бриф: запуск кампании"
    # travels via metadata too, so the rebuilt ExecutionContext reaches skills
    assert request.metadata["attachments"]["attached_documents"][0]["text"] == "Бриф: запуск кампании"


@pytest.mark.asyncio
async def test_ingest_download_failure_is_reported() -> None:
    sender = InMemoryTelegramSender()  # no downloads registered
    ingestor = MediaIngestor(sender, file_processor=FakeFileProcessor(), settings=_settings())

    result = await ingestor.ingest(
        [InboundMedia(kind="document", file_id="MISSING", filename="x.pdf")],
        user_input="go",
    )

    assert result.processed is False
    assert result.notes and "скачать" in result.notes[0].lower()
