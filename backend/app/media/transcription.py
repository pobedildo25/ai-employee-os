from __future__ import annotations

import logging

from app.core.config import Settings

logger = logging.getLogger(__name__)


class AudioTranscriber:
    """Transcribes audio via a Whisper-compatible ``/audio/transcriptions`` endpoint.

    OpenRouter does not expose transcription, so this talks to a configurable
    OpenAI-compatible service (OpenAI, Groq, a self-hosted Whisper, …). It is
    opt-in: when disabled or unconfigured, ``transcribe`` returns ``None`` and the
    caller degrades gracefully instead of failing the chat.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def enabled(self) -> bool:
        return bool(
            getattr(self._settings, "transcription_enabled", False)
            and self._api_key()
            and getattr(self._settings, "transcription_base_url", "")
        )

    def _api_key(self) -> str:
        return (
            getattr(self._settings, "transcription_api_key", "")
            or self._settings.openrouter_api_key
            or ""
        )

    async def transcribe(
        self,
        data: bytes,
        *,
        filename: str = "audio.ogg",
        mime_type: str | None = None,
        language: str | None = None,
    ) -> str | None:
        if not self.enabled:
            logger.info("transcription requested but disabled")
            return None

        import httpx

        base = self._settings.transcription_base_url.rstrip("/")
        url = f"{base}/audio/transcriptions"
        headers = {"Authorization": f"Bearer {self._api_key()}"}
        files = {"file": (filename, data, mime_type or "application/octet-stream")}
        payload: dict[str, str] = {"model": self._settings.transcription_model}
        if language:
            payload["language"] = language

        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(url, headers=headers, data=payload, files=files)
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPError as exc:
            logger.warning("transcription request failed | error=%s", exc)
            return None
        except Exception as exc:  # noqa: BLE001 - never break the chat
            logger.warning("transcription unexpected error | error=%s", exc)
            return None

        text = body.get("text") if isinstance(body, dict) else None
        return str(text).strip() if text else None
