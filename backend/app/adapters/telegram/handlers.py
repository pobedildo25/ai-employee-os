from typing import Any

from app.adapters.telegram.flow import TelegramProductFlow
from app.adapters.telegram.mapper import TelegramMapper
from app.adapters.telegram.models import TelegramExecutionRequest
from app.adapters.telegram.sender import TelegramSender
from app.adapters.telegram.session import TelegramSessionManager
from app.agent_runtime.runtime import AgentRuntime


class TelegramMessageHandler:
    """Legacy transport handler kept for tests and fallback."""

    def __init__(
        self,
        *,
        runtime: AgentRuntime,
        session_manager: TelegramSessionManager,
        sender: TelegramSender,
        mapper: TelegramMapper | None = None,
        product_flow: TelegramProductFlow | None = None,
    ) -> None:
        self._runtime = runtime
        self._sessions = session_manager
        self._sender = sender
        self._mapper = mapper or TelegramMapper()
        self._flow = product_flow

    async def handle(self, request: TelegramExecutionRequest) -> dict[str, Any]:
        if self._flow is not None:
            return await self._flow.handle_message(request)

        snapshot = await self._sessions.resolve(request.telegram_user_id)

        context = {
            **request.context,
            "client_id": snapshot["client_id"],
            "workspace_id": snapshot["workspace_id"],
            "project_id": snapshot.get("active_project_id"),
        }
        metadata = {
            **request.metadata,
            "client_id": snapshot["client_id"],
            "workspace_id": snapshot["workspace_id"],
            "session_id": snapshot.get("active_session_id"),
            "source": "telegram",
        }

        state = await self._runtime.execute(
            request.user_input,
            context=context,
            metadata=metadata,
        )
        state_dict = dict(state) if not isinstance(state, dict) else state
        reply = self._mapper.extract_reply_text(state_dict)

        send_result = await self._sender.send_message(
            request.telegram_chat_id,
            reply,
            reply_to_message_id=request.telegram_message_id,
        )

        return {
            "execution_id": state_dict.get("execution_id"),
            "trace_id": state_dict.get("trace_id"),
            "status": state_dict.get("status"),
            "reply": reply,
            "workspace_id": snapshot["workspace_id"],
            "send_result": send_result,
        }
