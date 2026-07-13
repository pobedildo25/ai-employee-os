"""Telegram implementations of conversation ports."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.adapters.telegram.continuation import TelegramArtifactDelivery
from app.adapters.telegram.keyboard import approval_keyboard, retry_keyboard
from app.adapters.telegram.progress import TelegramProgressMessenger
from app.adapters.telegram.sender import TelegramSender
from app.adapters.telegram.session import TelegramSessionManager


class TelegramSessionPort:
    """SessionPort backed by TelegramSessionManager + workspace history."""

    def __init__(self, session_manager: TelegramSessionManager) -> None:
        self._sessions = session_manager

    async def resolve(self, user_id: int) -> dict[str, Any]:
        return await self._sessions.resolve(user_id)

    async def release_db(self) -> None:
        await self._sessions.release_db()

    async def append_history(
        self,
        snapshot: dict[str, Any],
        *,
        role: str,
        content: str,
    ) -> None:
        conversation = snapshot.get("conversation") or {}
        conversation_id = conversation.get("id")
        session_id = snapshot.get("active_session_id")
        if not conversation_id and session_id:
            try:
                ensured = await self._sessions.workspace_manager.ensure_conversation(
                    UUID(str(session_id))
                )
                conversation_id = str(ensured.id)
            except Exception:
                return
        if not conversation_id or not content:
            return
        try:
            await self._sessions.workspace_manager.append_message(
                UUID(str(conversation_id)),
                {"role": role, "content": content},
            )
        except Exception:
            return

    async def set_active_artifact(self, workspace_id: str, artifact_id: str) -> None:
        try:
            await self._sessions.workspace_manager.set_active_artifact(
                UUID(str(workspace_id)),
                UUID(str(artifact_id)),
            )
        except Exception:
            return


class TelegramChannelNotifier:
    """ChannelNotifier using TelegramSender + keyboards + progress + artifact send."""

    def __init__(
        self,
        sender: TelegramSender,
        *,
        progress: TelegramProgressMessenger | None = None,
        artifact_delivery: TelegramArtifactDelivery | None = None,
    ) -> None:
        self._sender = sender
        self._progress = progress or TelegramProgressMessenger(sender)
        self._artifacts = artifact_delivery or TelegramArtifactDelivery(None, None)

    async def send_text(
        self,
        chat_id: int,
        text: str,
        *,
        reply_to_message_id: int | None = None,
    ) -> dict[str, Any]:
        return await self._sender.send_message(
            chat_id,
            text,
            reply_to_message_id=reply_to_message_id,
        )

    async def send_approval(self, chat_id: int, text: str) -> dict[str, Any]:
        return await self._sender.send_message(
            chat_id,
            text,
            reply_markup=approval_keyboard(),
        )

    async def send_retry(
        self,
        chat_id: int,
        text: str,
        *,
        progress_message_id: int | None = None,
    ) -> dict[str, Any]:
        markup = retry_keyboard()
        replaced = await self._progress.replace(
            chat_id,
            progress_message_id,
            text,
            reply_markup=markup,
        )
        if replaced is not None:
            return replaced
        if progress_message_id is not None:
            await self._progress.clear(chat_id, progress_message_id)
        return await self._sender.send_message(chat_id, text, reply_markup=markup)

    async def start_progress(
        self,
        chat_id: int,
        *,
        reply_to_message_id: int | None = None,
    ) -> int | None:
        return await self._progress.start(chat_id, reply_to_message_id=reply_to_message_id)

    async def update_progress(
        self,
        chat_id: int,
        message_id: int | None,
        progress: dict[str, Any] | None,
    ) -> int | None:
        return await self._progress.maybe_update(chat_id, message_id, progress)

    async def finalize_progress(
        self,
        chat_id: int,
        message_id: int | None,
        progress: dict[str, Any] | None,
    ) -> None:
        await self._progress.finalize(chat_id, message_id, progress)

    async def clear_progress(self, chat_id: int, message_id: int | None) -> None:
        await self._progress.clear(chat_id, message_id)

    async def send_artifacts(
        self,
        chat_id: int,
        artifacts: list[dict[str, Any]],
        *,
        caption: str | None = None,
    ) -> dict[str, Any]:
        last_index = len(artifacts) - 1
        sent = 0
        for index, artifact in enumerate(artifacts):
            try:
                data = await self._artifacts.download(artifact)
            except Exception:
                data = None
            if not data:
                continue
            try:
                await self._sender.send_document(
                    chat_id,
                    filename=str(artifact.get("name") or "artifact.bin"),
                    file_data=data,
                    mime_type=artifact.get("mime_type"),
                    caption=caption if index == last_index else None,
                )
                sent += 1
            except Exception:
                continue
        return {"ok": True, "via": "document_caption", "sent": sent}


class TelegramArtifactCollector:
    """ArtifactCollectorPort wrapping TelegramArtifactDelivery.collect_artifacts."""

    def __init__(self, delivery: TelegramArtifactDelivery | None = None) -> None:
        self._delivery = delivery or TelegramArtifactDelivery(None, None)

    async def collect_artifacts(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        return await self._delivery.collect_artifacts(state)
