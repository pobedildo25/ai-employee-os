from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class SessionPort(Protocol):
    async def resolve(self, user_id: int) -> dict[str, Any]: ...

    async def release_db(self) -> None: ...

    async def append_history(
        self,
        snapshot: dict[str, Any],
        *,
        role: str,
        content: str,
    ) -> None: ...

    async def set_active_artifact(
        self,
        workspace_id: str,
        artifact_id: str,
    ) -> None: ...


@runtime_checkable
class ChannelNotifier(Protocol):
    async def send_text(
        self,
        chat_id: int,
        text: str,
        *,
        reply_to_message_id: int | None = None,
    ) -> dict[str, Any]: ...

    async def send_approval(self, chat_id: int, text: str) -> dict[str, Any]: ...

    async def send_retry(
        self,
        chat_id: int,
        text: str,
        *,
        progress_message_id: int | None = None,
    ) -> dict[str, Any]: ...

    async def start_progress(
        self,
        chat_id: int,
        *,
        reply_to_message_id: int | None = None,
        header: str | None = None,
    ) -> int | None: ...

    async def update_progress(
        self,
        chat_id: int,
        message_id: int | None,
        progress: dict[str, Any] | None,
    ) -> int | None: ...

    async def finalize_progress(
        self,
        chat_id: int,
        message_id: int | None,
        progress: dict[str, Any] | None,
    ) -> None: ...

    async def clear_progress(self, chat_id: int, message_id: int | None) -> None: ...

    async def send_artifacts(
        self,
        chat_id: int,
        artifacts: list[dict[str, Any]],
        *,
        caption: str | None = None,
    ) -> dict[str, Any]: ...


@runtime_checkable
class RevisionContinuationPort(Protocol):
    async def continue_revision(
        self,
        prior_state: dict[str, Any],
        user_feedback: str,
    ) -> dict[str, Any]: ...


@runtime_checkable
class ArtifactCollectorPort(Protocol):
    async def collect_artifacts(self, state: dict[str, Any]) -> list[dict[str, Any]]: ...
