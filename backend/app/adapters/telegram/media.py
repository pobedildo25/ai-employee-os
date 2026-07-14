from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.adapters.telegram.models import InboundMedia
from app.adapters.telegram.sender import TelegramSender
from app.core.config import Settings, get_settings
from app.file_processing.processor import FileProcessor
from app.llm.gateway import LLMGateway
from app.media.transcription import AudioTranscriber

logger = logging.getLogger(__name__)

_AUDIO_KINDS = {"voice", "audio", "video_note"}


@dataclass
class MediaIngestResult:
    """Enriched context + user-facing notes produced from inbound attachments."""

    context: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    processed: bool = False


class MediaIngestor:
    """Turns inbound Telegram attachments into model-readable context.

    Documents are extracted to text, images are described with a vision model,
    and audio is transcribed (when a transcription endpoint is configured). The
    results are attached to the run context so the assistant can reason over them
    just like ChatGPT does with uploads.
    """

    def __init__(
        self,
        downloader: TelegramSender,
        *,
        file_processor: FileProcessor | None = None,
        gateway: LLMGateway | None = None,
        transcriber: AudioTranscriber | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._downloader = downloader
        self._files = file_processor or FileProcessor()
        self._gateway = gateway
        self._settings = settings or get_settings()
        self._transcriber = transcriber or AudioTranscriber(self._settings)

    async def ingest(self, media: list[InboundMedia], *, user_input: str) -> MediaIngestResult:
        result = MediaIngestResult()
        if not media:
            return result

        documents: list[dict[str, Any]] = []
        images: list[dict[str, Any]] = []
        transcripts: list[dict[str, Any]] = []

        for item in media:
            data = await self._download(item)
            if data is None:
                result.notes.append(f"Не удалось скачать вложение ({item.kind}).")
                continue

            try:
                if item.kind == "document":
                    self._ingest_document(item, data, documents, result)
                elif item.kind == "photo":
                    await self._ingest_image(item, data, images, result, user_input)
                elif item.kind in _AUDIO_KINDS:
                    await self._ingest_audio(item, data, transcripts, result)
            except Exception as exc:  # noqa: BLE001 - attachment failure must not break chat
                logger.warning("media ingest failed | kind=%s error=%s", item.kind, exc)
                result.notes.append(f"Не удалось обработать вложение ({item.kind}).")

        if documents:
            result.context["attached_documents"] = documents
        if images:
            result.context["attached_images"] = images
        if transcripts:
            result.context["attached_transcripts"] = transcripts
        result.processed = bool(documents or images or transcripts)
        return result

    async def _download(self, item: InboundMedia) -> bytes | None:
        try:
            return await self._downloader.download_file(item.file_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("download failed | file_id=%s error=%s", item.file_id, exc)
            return None

    def _ingest_document(
        self,
        item: InboundMedia,
        data: bytes,
        documents: list[dict[str, Any]],
        result: MediaIngestResult,
    ) -> None:
        filename = item.filename or "document"
        extracted = self._files.process_bytes(data, filename, mime_type=item.mime_type)
        text = (extracted.text or "").strip()
        limit = int(getattr(self._settings, "attachment_max_chars", 6000))
        truncated = len(text) > limit
        documents.append(
            {
                "title": filename,
                "mime_type": item.mime_type,
                "pages": extracted.pages,
                "text": text[:limit],
                "truncated": truncated,
            }
        )
        result.notes.append(f"Документ «{filename}» прочитан.")

    async def _ingest_image(
        self,
        item: InboundMedia,
        data: bytes,
        images: list[dict[str, Any]],
        result: MediaIngestResult,
        user_input: str,
    ) -> None:
        description: str | None = None
        if self._gateway is not None and getattr(self._settings, "vision_enabled", False):
            prompt = user_input.strip() or "Опиши подробно, что изображено на картинке."
            try:
                description = await self._gateway.vision(
                    prompt,
                    [(data, item.mime_type or "image/jpeg")],
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("vision failed | error=%s", exc)

        if not description:
            # Fallback: OCR any embedded text via the image extractor.
            try:
                extracted = self._files.process_bytes(data, item.filename or "image.jpg", mime_type=item.mime_type)
                description = (extracted.text or "").strip() or None
            except Exception:  # noqa: BLE001
                description = None

        if description:
            images.append({"description": description, "mime_type": item.mime_type})
            result.notes.append("Изображение проанализировано.")
        else:
            result.notes.append("Изображение получено, но распознать содержимое не удалось.")

    async def _ingest_audio(
        self,
        item: InboundMedia,
        data: bytes,
        transcripts: list[dict[str, Any]],
        result: MediaIngestResult,
    ) -> None:
        transcript = await self._transcriber.transcribe(
            data,
            filename=item.filename or f"{item.kind}.ogg",
            mime_type=item.mime_type,
            language="ru",
        )
        if transcript:
            transcripts.append(
                {"transcript": transcript, "duration": item.duration, "kind": item.kind}
            )
            result.notes.append("Аудио расшифровано.")
        else:
            result.notes.append(
                "Аудио получено, но расшифровка недоступна. "
                "Включите транскрипцию (TRANSCRIPTION_ENABLED) для анализа звонков."
            )
