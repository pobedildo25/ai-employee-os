from typing import Any
import uuid

from app.agent_runtime.exceptions import GraphExecutionError
from app.agent_runtime.state.models import create_initial_state
from app.adapters.telegram.clarification import build_pending_clarification, merge_clarification_answer
from app.adapters.telegram.conversation_store import TelegramConversationState, TelegramFlowMode
from app.adapters.telegram.continuation import TelegramArtifactDelivery, TelegramGraphContinuation
from app.adapters.telegram.keyboard import approval_keyboard, retry_keyboard, revision_keyboard
from app.adapters.telegram.mapper import TelegramMapper
from app.adapters.telegram.models import TelegramCallbackRequest, TelegramExecutionRequest
from app.adapters.telegram.presenter import (
    extract_failure_reason,
    format_approval_message,
    format_completion_message,
    format_delivery_summary,
    format_error_message,
    format_revision_prompt,
    format_runtime_error_message,
)
from app.adapters.telegram.progress import TelegramProgressMessenger
from app.adapters.telegram.revision import is_contextual_revision_message
from app.adapters.telegram.sender import TelegramSender
from app.adapters.telegram.session import TelegramSessionManager
from app.agent_runtime.runtime import AgentRuntime
from app.agents.executive.agent import ExecutiveAgent
from app.agents.intent.policy import extract_chat_reply, is_chat_decision, is_task_decision
from app.clients.resolver import BusinessClientResolver
from app.orchestration.orchestrator import Orchestrator
from app.ux.status_copy import STATUS_LOOKING, STATUS_WORKING


class TelegramProductFlow:
    """Telegram product UX over existing runtime, orchestrator, and revision nodes."""

    def __init__(
        self,
        *,
        runtime: AgentRuntime,
        session_manager: TelegramSessionManager,
        sender: TelegramSender,
        conversation_store,
        mapper: TelegramMapper | None = None,
        progress_messenger: TelegramProgressMessenger | None = None,
        continuation: TelegramGraphContinuation | None = None,
        artifact_delivery: TelegramArtifactDelivery | None = None,
        orchestrator: Orchestrator | None = None,
        executive_agent: ExecutiveAgent | None = None,
        business_client_resolver: BusinessClientResolver | None = None,
    ) -> None:
        self._runtime = runtime
        self._sessions = session_manager
        self._sender = sender
        self._store = conversation_store
        self._mapper = mapper or TelegramMapper()
        self._progress = progress_messenger or TelegramProgressMessenger(sender)
        self._continuation = continuation
        self._artifacts = artifact_delivery or TelegramArtifactDelivery(None, None)
        self._orchestrator = orchestrator or Orchestrator()
        self._executive_agent = executive_agent
        self._business_client_resolver = business_client_resolver

    async def handle_message(self, request: TelegramExecutionRequest) -> dict[str, Any]:
        convo = self._store.get_or_create(request.telegram_user_id, request.telegram_chat_id)
        snapshot = await self._sessions.resolve(request.telegram_user_id)
        convo.workspace_id = snapshot.get("workspace_id")
        convo.session_id = snapshot.get("active_session_id")

        if convo.flow_mode == TelegramFlowMode.REVISION_PROMPTED:
            return await self._handle_revision_feedback(request, convo, snapshot)

        if convo.flow_mode == TelegramFlowMode.COMPLETED and is_contextual_revision_message(request.user_input):
            return await self._handle_revision_feedback(request, convo, snapshot, contextual=True)

        if convo.pending_clarification is not None:
            return await self._resume_pending_clarification(request, convo, snapshot)

        status_message_id = await self._progress.start(
            request.telegram_chat_id,
            reply_to_message_id=request.telegram_message_id,
            text=STATUS_LOOKING,
        )
        convo.progress_message_id = status_message_id
        self._store.save(convo)

        classification = await self._classify_intent(request, snapshot)
        if classification is not None:
            if is_chat_decision(classification.decision.action.value):
                return await self._handle_chat_response(
                    request,
                    convo,
                    classification,
                    status_message_id=status_message_id,
                )
            if is_task_decision(classification.decision.action.value):
                await self._progress.set_text(
                    request.telegram_chat_id,
                    status_message_id,
                    STATUS_WORKING,
                )
                return await self._run_execution(
                    request,
                    convo,
                    snapshot,
                    progress_message_id=status_message_id,
                )

        await self._progress.set_text(
            request.telegram_chat_id,
            status_message_id,
            STATUS_WORKING,
        )
        return await self._run_execution(
            request,
            convo,
            snapshot,
            progress_message_id=status_message_id,
        )

    async def _classify_intent(
        self,
        request: TelegramExecutionRequest,
        snapshot: dict[str, Any],
    ):
        if self._executive_agent is None:
            return None
        context, metadata = self._build_runtime_payload(request, snapshot)
        state = create_initial_state(
            execution_id=uuid.uuid4().hex,
            trace_id=uuid.uuid4().hex[:16],
            user_input=request.user_input,
            context=context,
            metadata={**metadata, "intent_classification": True},
        )
        return await self._executive_agent.analyze(state)

    async def _handle_chat_response(
        self,
        request: TelegramExecutionRequest,
        convo: TelegramConversationState,
        classification,
        *,
        status_message_id: int | None = None,
    ) -> dict[str, Any]:
        action = classification.decision.action.value
        if action == "ASK_CLARIFICATION":
            convo.flow_mode = TelegramFlowMode.PENDING_CLARIFICATION
            convo.pending_clarification = build_pending_clarification(
                user_input=request.user_input,
                classification=classification,
            )
            convo.last_user_input = request.user_input
            convo.last_execution_id = None
            convo.last_agent_state = None
            self._store.save(convo)

            text = extract_chat_reply(classification.decision.model_dump()) or (
                "Уточните, пожалуйста, детали задачи."
            )
            send_result = await self._deliver_status_or_send(
                request,
                status_message_id,
                text,
            )
            return {
                "status": "clarification",
                "intent": "chat",
                "reply": text,
                "decision": classification.decision.model_dump(),
                "workspace_id": convo.workspace_id,
                "send_result": send_result,
            }

        convo.flow_mode = TelegramFlowMode.COMPLETED
        convo.pending_clarification = None
        convo.last_user_input = request.user_input
        convo.last_execution_id = None
        convo.last_agent_state = None
        self._store.save(convo)

        text = extract_chat_reply(classification.decision.model_dump()) or "Привет! Я NOVA — AI-сотрудник агентства."
        send_result = await self._deliver_status_or_send(
            request,
            status_message_id,
            text,
        )
        return {
            "status": "completed",
            "intent": "chat",
            "reply": text,
            "decision": classification.decision.model_dump(),
            "workspace_id": convo.workspace_id,
            "send_result": send_result,
        }

    async def _deliver_status_or_send(
        self,
        request: TelegramExecutionRequest,
        status_message_id: int | None,
        text: str,
    ) -> dict[str, Any]:
        if status_message_id is not None:
            return await self._sender.edit_message_text(
                request.telegram_chat_id,
                status_message_id,
                text,
            )
        return await self._sender.send_message(
            request.telegram_chat_id,
            text,
            reply_to_message_id=request.telegram_message_id,
        )

    async def _resume_pending_clarification(
        self,
        request: TelegramExecutionRequest,
        convo: TelegramConversationState,
        snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        pending = convo.pending_clarification
        if pending is None:
            return await self._run_execution(request, convo, snapshot)

        merged_input = merge_clarification_answer(pending, request.user_input)
        convo.pending_clarification = None
        convo.flow_mode = TelegramFlowMode.IDLE
        self._store.save(convo)

        merged_request = request.model_copy(update={"user_input": merged_input})
        result = await self._run_execution(merged_request, convo, snapshot)
        result["resumed_from_clarification"] = True
        result["merged_input"] = merged_input
        return result

    async def handle_callback(self, request: TelegramCallbackRequest) -> dict[str, Any]:
        convo = self._store.get_or_create(request.telegram_user_id, request.telegram_chat_id)
        snapshot = await self._sessions.resolve(request.telegram_user_id)

        if request.action == "approve":
            return await self._handle_approval_resume(convo, snapshot)
        if request.action == "cancel":
            return await self._handle_cancel(convo, request)
        if request.action == "revise":
            return await self._handle_revise_prompt(convo, request)
        if request.action == "retry":
            return await self._handle_retry(convo, snapshot, request)

        return {"status": "ignored", "action": request.action}

    async def _run_execution(
        self,
        request: TelegramExecutionRequest,
        convo: TelegramConversationState,
        snapshot: dict[str, Any],
        *,
        progress_message_id: int | None = None,
    ) -> dict[str, Any]:
        context, metadata = self._build_runtime_payload(request, snapshot)
        await self._attach_business_client(request, convo, context)
        convo.flow_mode = TelegramFlowMode.RUNNING
        convo.last_user_input = request.user_input
        self._store.save(convo)

        if progress_message_id is None:
            progress_message_id = await self._progress.start(
                request.telegram_chat_id,
                reply_to_message_id=request.telegram_message_id,
                text=STATUS_WORKING,
            )
        else:
            await self._progress.set_text(
                request.telegram_chat_id,
                progress_message_id,
                STATUS_WORKING,
            )
        convo.progress_message_id = progress_message_id
        self._store.save(convo)

        try:
            state = await self._execute_with_progress(
                request.user_input,
                chat_id=request.telegram_chat_id,
                progress_message_id=progress_message_id,
                context=context,
                metadata=metadata,
            )
        except GraphExecutionError as exc:
            return await self._handle_execution_failure(
                request,
                convo,
                progress_message_id,
                exc,
            )
        except Exception as exc:
            return await self._handle_execution_failure(
                request,
                convo,
                progress_message_id,
                GraphExecutionError(str(exc)),
            )

        state_dict = dict(state) if not isinstance(state, dict) else state
        return await self._deliver_outcome(request, convo, state_dict, progress_message_id)

    async def _handle_execution_failure(
        self,
        request: TelegramExecutionRequest,
        convo: TelegramConversationState,
        progress_message_id: int | None,
        exc: GraphExecutionError,
    ) -> dict[str, Any]:
        convo.flow_mode = TelegramFlowMode.FAILED
        self._store.save(convo)
        await self._progress.dismiss(request.telegram_chat_id, progress_message_id)

        reason = _safe_error_reason(str(exc))
        text = format_runtime_error_message(
            trace_id=getattr(exc, "trace_id", None),
            execution_id=getattr(exc, "execution_id", None),
            reason=reason,
        )
        send_result = await self._sender.send_message(
            request.telegram_chat_id,
            text,
            reply_markup=retry_keyboard(),
        )
        return {
            "status": "failed",
            "error": "execution_failed",
            "trace_id": getattr(exc, "trace_id", None),
            "execution_id": getattr(exc, "execution_id", None),
            "send_result": send_result,
        }

    async def _execute_with_progress(
        self,
        user_input: str,
        *,
        chat_id: int,
        progress_message_id: int | None,
        context: dict[str, Any],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        final_state: dict[str, Any] | None = None
        last_progress: dict[str, Any] | None = None

        async for event in self._runtime.stream(
            user_input,
            context=context,
            metadata=metadata,
        ):
            if not isinstance(event, dict):
                continue
            for update in event.values():
                if not isinstance(update, dict):
                    continue
                if update.get("telegram_progress"):
                    last_progress = update["telegram_progress"]
                    progress_message_id = await self._progress.maybe_update(
                        chat_id,
                        progress_message_id,
                        last_progress,
                    )
                final_state = self._merge_state(final_state, update)

        if final_state is not None:
            await self._progress.finalize(chat_id, progress_message_id, last_progress)
            return final_state

        state = await self._runtime.execute(
            user_input,
            context=context,
            metadata=metadata,
        )
        state_dict = dict(state) if not isinstance(state, dict) else state
        await self._progress.finalize(chat_id, progress_message_id, state_dict.get("telegram_progress"))
        return state_dict

    async def _deliver_outcome(
        self,
        request: TelegramExecutionRequest,
        convo: TelegramConversationState,
        state: dict[str, Any],
        progress_message_id: int | None,
    ) -> dict[str, Any]:
        convo.last_execution_id = state.get("execution_id")
        convo.last_agent_state = state
        status = str(state.get("status") or "")

        if status == "waiting_approval":
            convo.flow_mode = TelegramFlowMode.WAITING_APPROVAL
            self._store.save(convo)
            text = format_approval_message(state.get("task_plan"))
            send_result = await self._sender.send_message(
                request.telegram_chat_id,
                text,
                reply_markup=approval_keyboard(),
            )
            return {
                "execution_id": state.get("execution_id"),
                "status": status,
                "reply": text,
                "send_result": send_result,
            }

        if status in {"execution_failed", "failed"} or status.endswith("_failed"):
            convo.flow_mode = TelegramFlowMode.FAILED
            self._store.save(convo)
            reason = extract_failure_reason(state)
            text = format_error_message(reason)
            send_result = await self._sender.send_message(
                request.telegram_chat_id,
                text,
                reply_markup=retry_keyboard(),
            )
            return {
                "execution_id": state.get("execution_id"),
                "status": status,
                "reply": text,
                "send_result": send_result,
            }

        convo.flow_mode = TelegramFlowMode.COMPLETED
        artifacts = await self._artifacts.collect_artifacts(state)
        convo.artifact_ids = [item.get("id") for item in artifacts if item.get("id")]
        self._store.save(convo)

        await self._send_artifact_files(request.telegram_chat_id, artifacts)

        if artifacts:
            summary = format_delivery_summary(artifacts, state)
            send_result = await self._sender.send_message(
                request.telegram_chat_id,
                summary,
                reply_markup=revision_keyboard(),
            )
            reply = summary
        else:
            reply = self._mapper.extract_reply_text(state)
            completion = format_completion_message(state)
            send_result = await self._sender.send_message(
                request.telegram_chat_id,
                completion if status == "completed" else reply,
                reply_markup=revision_keyboard() if status == "completed" else None,
            )
            reply = completion if status == "completed" else reply

        return {
            "execution_id": state.get("execution_id"),
            "trace_id": state.get("trace_id"),
            "status": status,
            "reply": reply,
            "workspace_id": convo.workspace_id,
            "send_result": send_result,
            "progress_message_id": progress_message_id,
        }

    async def _handle_approval_resume(
        self,
        convo: TelegramConversationState,
        snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        if convo.flow_mode != TelegramFlowMode.WAITING_APPROVAL or not convo.last_user_input:
            text = "Сейчас нет плана, ожидающего подтверждения."
            send_result = await self._sender.send_message(convo.telegram_chat_id, text)
            return {"status": "noop", "reply": text, "send_result": send_result}

        request = TelegramExecutionRequest(
            user_input=convo.last_user_input,
            telegram_user_id=convo.telegram_user_id,
            telegram_chat_id=convo.telegram_chat_id,
            metadata={"auto_approve": True, "source": "telegram"},
            context={"channel": "telegram"},
        )
        return await self._run_execution(request, convo, snapshot)

    async def _handle_cancel(
        self,
        convo: TelegramConversationState,
        request: TelegramCallbackRequest,
    ) -> dict[str, Any]:
        if convo.last_execution_id:
            self._orchestrator.cancel_execution(convo.last_execution_id)
        convo.flow_mode = TelegramFlowMode.CANCELLED
        self._store.save(convo)
        text = "Выполнение отменено."
        send_result = await self._sender.send_message(convo.telegram_chat_id, text)
        return {"status": "cancelled", "reply": text, "send_result": send_result}

    async def _handle_revise_prompt(
        self,
        convo: TelegramConversationState,
        request: TelegramCallbackRequest,
    ) -> dict[str, Any]:
        from datetime import datetime

        convo.flow_mode = TelegramFlowMode.REVISION_PROMPTED
        convo.revision_prompted_at = datetime.now()
        self._store.save(convo)
        text = format_revision_prompt()
        send_result = await self._sender.send_message(convo.telegram_chat_id, text)
        return {"status": "revision_prompted", "reply": text, "send_result": send_result}

    async def _handle_revision_feedback(
        self,
        request: TelegramExecutionRequest,
        convo: TelegramConversationState,
        snapshot: dict[str, Any],
        *,
        contextual: bool = False,
    ) -> dict[str, Any]:
        if not convo.last_agent_state or self._continuation is None:
            text = "Сначала нужно получить результат, прежде чем вносить правки."
            send_result = await self._sender.send_message(request.telegram_chat_id, text)
            return {"status": "revision_unavailable", "reply": text, "send_result": send_result}

        try:
            state = await self._continuation.continue_revision(
                convo.last_agent_state,
                request.user_input,
            )
        except Exception as exc:
            text = format_error_message(str(exc))
            send_result = await self._sender.send_message(
                request.telegram_chat_id,
                text,
                reply_markup=retry_keyboard(),
            )
            return {"status": "revision_failed", "reply": text, "send_result": send_result}

        convo.last_agent_state = state
        convo.flow_mode = TelegramFlowMode.COMPLETED
        convo.revision_prompted_at = None
        self._store.save(convo)

        artifacts = await self._artifacts.collect_artifacts(state)
        await self._send_artifact_files(request.telegram_chat_id, artifacts)

        if artifacts:
            reply = format_delivery_summary(artifacts, state)
        else:
            reply = format_completion_message(state)

        send_result = await self._sender.send_message(
            request.telegram_chat_id,
            reply,
            reply_markup=revision_keyboard(),
        )
        return {
            "status": "revised",
            "contextual": contextual,
            "reply": reply,
            "send_result": send_result,
        }

    async def _handle_retry(
        self,
        convo: TelegramConversationState,
        snapshot: dict[str, Any],
        request: TelegramCallbackRequest,
    ) -> dict[str, Any]:
        if not convo.last_user_input:
            text = "Нечего повторить. Опишите задачу текстом."
            send_result = await self._sender.send_message(convo.telegram_chat_id, text)
            return {"status": "noop", "reply": text, "send_result": send_result}

        exec_request = TelegramExecutionRequest(
            user_input=convo.last_user_input,
            telegram_user_id=convo.telegram_user_id,
            telegram_chat_id=convo.telegram_chat_id,
            metadata={"source": "telegram", "telegram_retry": True},
            context={"channel": "telegram"},
        )
        return await self._run_execution(exec_request, convo, snapshot)

    async def _send_artifact_files(self, chat_id: int, artifacts: list[dict[str, Any]]) -> None:
        for artifact in artifacts:
            data = await self._artifacts.download(artifact)
            if not data:
                continue
            await self._sender.send_document(
                chat_id,
                filename=str(artifact.get("name") or "artifact.bin"),
                file_data=data,
                mime_type=artifact.get("mime_type"),
            )

    async def _attach_business_client(
        self,
        request: TelegramExecutionRequest,
        convo: TelegramConversationState,
        context: dict[str, Any],
    ) -> None:
        """Find-or-create the business client this task is for and route the run to it.

        The run context's ``client_id``/``project_id`` are pointed at the real
        business client so artifacts land under it and client intelligence runs
        against it. The workspace/session binding stays on the transport identity
        (kept in metadata), so this is additive and safe when no client is named.
        """
        if self._business_client_resolver is None:
            return
        try:
            resolved = await self._business_client_resolver.resolve(
                request.user_input,
                trace_id=str(request.metadata.get("trace_id") or "-"),
            )
        except Exception:  # resolution must never break task execution
            return
        if resolved is None:
            return

        context["client_id"] = str(resolved.client_id)
        context["business_client_id"] = str(resolved.client_id)
        context["client_name"] = resolved.name
        if resolved.project_id is not None:
            context["project_id"] = str(resolved.project_id)
        convo.business_client_id = str(resolved.client_id)
        convo.business_client_name = resolved.name

    def _build_runtime_payload(
        self,
        request: TelegramExecutionRequest,
        snapshot: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        context = {
            **request.context,
            "client_id": snapshot["client_id"],
            "workspace_id": snapshot["workspace_id"],
            "project_id": snapshot.get("active_project_id"),
            "channel": "telegram",
        }
        metadata = {
            **request.metadata,
            "client_id": snapshot["client_id"],
            "workspace_id": snapshot["workspace_id"],
            "session_id": snapshot.get("active_session_id"),
            "source": "telegram",
        }
        if snapshot.get("active_artifact_id"):
            metadata["active_artifact_id"] = snapshot["active_artifact_id"]
        return context, metadata

    @staticmethod
    def _merge_state(current: dict[str, Any] | None, update: dict[str, Any]) -> dict[str, Any]:
        if current is None:
            return dict(update)
        merged = dict(current)
        merged.update(update)
        return merged


def _safe_error_reason(message: str) -> str | None:
    if not message:
        return None
    lowered = message.lower()
    if "traceback" in lowered:
        return None
    if message.startswith("Workflow "):
        _, _, tail = message.partition(": ")
        return tail or message
    return message
