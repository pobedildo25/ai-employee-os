from abc import ABC, abstractmethod
from typing import Any


class TelegramSender(ABC):
    """Sends messages to Telegram — no text generation."""

    @abstractmethod
    async def send_message(
        self,
        chat_id: int,
        text: str,
        *,
        reply_to_message_id: int | None = None,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def send_document(
        self,
        chat_id: int,
        *,
        filename: str,
        file_data: bytes,
        mime_type: str | None = None,
        caption: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def download_file(self, file_id: str) -> bytes | None:
        """Download an inbound Telegram file by file_id (getFile + fetch).

        Returns raw bytes, or ``None`` when the file cannot be retrieved.
        Not abstract so existing doubles keep working without media support.
        """
        return None


class HttpTelegramSender(TelegramSender):
    def __init__(self, token: str, *, api_base: str = "https://api.telegram.org") -> None:
        self._token = token
        self._api_base = api_base.rstrip("/")

    async def send_message(
        self,
        chat_id: int,
        text: str,
        *,
        reply_to_message_id: int | None = None,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if reply_to_message_id is not None:
            payload["reply_to_message_id"] = reply_to_message_id
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return await self._post("sendMessage", payload)

    async def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return await self._post("editMessageText", payload)

    async def send_document(
        self,
        chat_id: int,
        *,
        filename: str,
        file_data: bytes,
        mime_type: str | None = None,
        caption: str | None = None,
    ) -> dict[str, Any]:
        import httpx

        data = {"chat_id": str(chat_id)}
        if caption:
            data["caption"] = caption
        files = {"document": (filename, file_data, mime_type or "application/octet-stream")}
        url = f"{self._api_base}/bot{self._token}/sendDocument"
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, data=data, files=files)
            response.raise_for_status()
            return response.json()

    async def download_file(self, file_id: str) -> bytes | None:
        import logging

        import httpx

        logger = logging.getLogger(__name__)
        try:
            meta = await self._post("getFile", {"file_id": file_id})
            file_path = (meta.get("result") or {}).get("file_path")
            if not file_path:
                logger.warning("getFile returned no file_path | file_id=%s", file_id)
                return None
            url = f"{self._api_base}/file/bot{self._token}/{file_path}"
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.content
        except httpx.HTTPError as exc:
            logger.warning("telegram file download failed | file_id=%s error=%s", file_id, exc)
            return None

    async def _post(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        import httpx

        url = f"{self._api_base}/bot{self._token}/{method}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()


class InMemoryTelegramSender(TelegramSender):
    """Test/double sender that records outbound messages."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.edited: list[dict[str, Any]] = []
        self.documents: list[dict[str, Any]] = []
        self.downloads: dict[str, bytes] = {}
        self.download_calls: list[str] = []
        self._message_counter = 1000

    async def send_message(
        self,
        chat_id: int,
        text: str,
        *,
        reply_to_message_id: int | None = None,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._message_counter += 1
        record = {
            "chat_id": chat_id,
            "text": text,
            "reply_to_message_id": reply_to_message_id,
            "reply_markup": reply_markup,
            "message_id": self._message_counter,
        }
        self.sent.append(record)
        return {"ok": True, "result": record}

    async def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        record = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "reply_markup": reply_markup,
        }
        self.edited.append(record)
        return {"ok": True, "result": record}

    async def send_document(
        self,
        chat_id: int,
        *,
        filename: str,
        file_data: bytes,
        mime_type: str | None = None,
        caption: str | None = None,
    ) -> dict[str, Any]:
        record = {
            "chat_id": chat_id,
            "filename": filename,
            "size": len(file_data),
            "mime_type": mime_type,
            "caption": caption,
        }
        self.documents.append(record)
        return {"ok": True, "result": record}

    async def download_file(self, file_id: str) -> bytes | None:
        self.download_calls.append(file_id)
        return self.downloads.get(file_id)
