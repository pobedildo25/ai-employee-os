from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from functools import lru_cache
from uuid import UUID, uuid5, NAMESPACE_URL

import redis.asyncio as aioredis

from app.clients.classification import telegram_user_client_metadata
from app.repositories.client_repository import ClientRepository
from app.workspace.manager import WorkspaceManager
from app.workspace.service import WorkspaceService

logger = logging.getLogger(__name__)

BINDING_KEY = "conversation:binding:{user_id}"
BINDING_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days

DbRelease = Callable[[], Awaitable[None]]


def telegram_client_id(telegram_user_id: int) -> UUID:
    """Stable workspace client identity for a Telegram user (transport binding only)."""
    return uuid5(NAMESPACE_URL, f"telegram:user:{telegram_user_id}")


@lru_cache
def get_session_bindings_singleton() -> dict[int, UUID]:
    """Process-lifetime telegram_user_id → workspace_id bindings (in-memory cache / tests)."""
    return {}


class TelegramSessionManager:
    """Links telegram_user_id → Workspace → Session via existing WorkspaceManager."""

    def __init__(
        self,
        workspace_service: WorkspaceService | None = None,
        workspace_manager: WorkspaceManager | None = None,
        client_repository: ClientRepository | None = None,
        bindings: dict[int, UUID] | None = None,
        redis_client: aioredis.Redis | None = None,
        db_release: DbRelease | None = None,
    ) -> None:
        if workspace_service is not None:
            self._service = workspace_service
        else:
            self._service = WorkspaceService(workspace_manager or WorkspaceManager())
        self._client_repository = client_repository
        # Explicit bindings={} keeps tests fully in-memory (no Redis side effects).
        self._bindings: dict[int, UUID] = (
            bindings if bindings is not None else get_session_bindings_singleton()
        )
        self._redis = None if bindings is not None else redis_client
        self._db_release = db_release

    @property
    def workspace_manager(self) -> WorkspaceManager:
        return self._service.manager

    async def release_db(self) -> None:
        """Commit/release the request DB session before long LLM work (P1-I)."""
        if self._db_release is not None:
            await self._db_release()

    async def resolve(self, telegram_user_id: int) -> dict:
        """Reuse Workspace/Session for the Telegram user across updates."""
        client_id = telegram_client_id(telegram_user_id)
        existing_id = self._bindings.get(telegram_user_id)
        if existing_id is None:
            existing_id = await self._load_binding(telegram_user_id)
            if existing_id is not None:
                self._bindings[telegram_user_id] = existing_id

        if existing_id is not None:
            snapshot = await self._service.get_snapshot(existing_id)
            if snapshot is not None and snapshot.get("active_session_id"):
                return snapshot

        if self._client_repository is not None:
            await self._client_repository.get_or_create_with_id(
                client_id,
                name=f"Telegram {telegram_user_id}",
                description="Telegram transport identity (not a business client)",
                metadata=telegram_user_client_metadata(telegram_user_id),
            )

        # Prefer durable workspace lookup over always opening a new session.
        existing = await self._service.get_snapshot_for_client(client_id)
        if existing is not None and existing.get("active_session_id"):
            workspace_id = UUID(existing["workspace_id"])
            await self._bind(telegram_user_id, workspace_id)
            return existing

        snapshot = await self._service.ensure_session_for_client(
            client_id=client_id,
            metadata={"source": "telegram", "telegram_user_id": telegram_user_id},
        )
        await self._bind(telegram_user_id, UUID(snapshot["workspace_id"]))
        return snapshot

    def get_bound_workspace_id(self, telegram_user_id: int) -> UUID | None:
        return self._bindings.get(telegram_user_id)

    async def _bind(self, telegram_user_id: int, workspace_id: UUID) -> None:
        self._bindings[telegram_user_id] = workspace_id
        await self._persist_binding(telegram_user_id, workspace_id)

    async def _load_binding(self, telegram_user_id: int) -> UUID | None:
        if self._redis is None:
            return None
        try:
            raw = await self._redis.get(BINDING_KEY.format(user_id=telegram_user_id))
        except Exception as exc:
            logger.warning("redis binding load failed | user_id=%s error=%s", telegram_user_id, exc)
            return None
        if not raw:
            return None
        try:
            return UUID(str(raw))
        except ValueError:
            return None

    async def _persist_binding(self, telegram_user_id: int, workspace_id: UUID) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.set(
                BINDING_KEY.format(user_id=telegram_user_id),
                str(workspace_id),
                ex=BINDING_TTL_SECONDS,
            )
        except Exception as exc:
            logger.warning(
                "redis binding persist failed | user_id=%s error=%s",
                telegram_user_id,
                exc,
            )
