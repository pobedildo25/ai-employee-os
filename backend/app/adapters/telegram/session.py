from functools import lru_cache
from uuid import UUID, uuid5, NAMESPACE_URL

from app.clients.classification import telegram_user_client_metadata
from app.repositories.client_repository import ClientRepository
from app.workspace.manager import WorkspaceManager
from app.workspace.service import WorkspaceService


def telegram_client_id(telegram_user_id: int) -> UUID:
    """Stable workspace client identity for a Telegram user (transport binding only)."""
    return uuid5(NAMESPACE_URL, f"telegram:user:{telegram_user_id}")


@lru_cache
def get_session_bindings_singleton() -> dict[int, UUID]:
    """Process-lifetime telegram_user_id → workspace_id bindings."""
    return {}


class TelegramSessionManager:
    """Links telegram_user_id → Workspace → Session via existing WorkspaceManager."""

    def __init__(
        self,
        workspace_service: WorkspaceService | None = None,
        workspace_manager: WorkspaceManager | None = None,
        client_repository: ClientRepository | None = None,
        bindings: dict[int, UUID] | None = None,
    ) -> None:
        if workspace_service is not None:
            self._service = workspace_service
        else:
            self._service = WorkspaceService(workspace_manager or WorkspaceManager())
        self._client_repository = client_repository
        self._bindings: dict[int, UUID] = (
            bindings if bindings is not None else get_session_bindings_singleton()
        )

    @property
    def workspace_manager(self) -> WorkspaceManager:
        return self._service.manager

    async def resolve(self, telegram_user_id: int) -> dict:
        """Reuse Workspace/Session for the Telegram user across updates."""
        client_id = telegram_client_id(telegram_user_id)
        existing_id = self._bindings.get(telegram_user_id)

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
            self._bindings[telegram_user_id] = UUID(existing["workspace_id"])
            return existing

        snapshot = await self._service.ensure_session_for_client(
            client_id=client_id,
            metadata={"source": "telegram", "telegram_user_id": telegram_user_id},
        )
        self._bindings[telegram_user_id] = UUID(snapshot["workspace_id"])
        return snapshot

    def get_bound_workspace_id(self, telegram_user_id: int) -> UUID | None:
        return self._bindings.get(telegram_user_id)
