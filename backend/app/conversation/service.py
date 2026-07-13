from typing import Any
import uuid
from uuid import UUID

from app.agent_runtime.exceptions import GraphExecutionError
from app.agent_runtime.state.models import create_initial_state
from app.adapters.telegram.continuation import TelegramArtifactDelivery, TelegramGraphContinuation
from app.adapters.telegram.keyboard import approval_keyboard, retry_keyboard
from app.adapters.telegram.mapper import TelegramMapper
from app.adapters.telegram.models import TelegramCallbackRequest, TelegramExecutionRequest
from app.adapters.telegram.presenter import (
    extract_failure_reason,
    format_approval_message,
    format_completion_message,
    format_delivery_caption,
    format_delivery_summary,
    format_error_message,
    format_revision_prompt,
    format_runtime_error_message,
    has_real_result_message,
)
from app.adapters.telegram.progress import TelegramProgressMessenger
from app.adapters.telegram.sender import TelegramSender
from app.adapters.telegram.session import TelegramSessionManager
from app.agent_runtime.runtime import AgentRuntime
from app.agents.decision.policy import is_clarification, is_respond
from app.agents.executive.agent import ExecutiveAgent
from app.agents.intent.policy import extract_chat_reply, is_chat_decision, is_task_decision
from app.conversation.clarification import build_pending_clarification, merge_clarification_answer
from app.conversation.models import ConversationState, FlowMode, PendingClarification
from app.orchestration.orchestrator import Orchestrator

# Channel DTOs (TelegramExecutionRequest / TelegramCallbackRequest) are temporary until
# multi-channel ports land; ConversationService is the channel-neutral dialog FSM.


class ConversationService:
    """Channel-neutral product UX over existing runtime, orchestrator, and revision nodes."""

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
        allowed_user_ids: set[int] | None = None,
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
        self._allowed_user_ids = allowed_user_ids or set()

    async def handle_message(self, request: TelegramExecutionRequest) -> dict[str, Any]:
        if self._allowed_user_ids and request.telegram_user_id not in self._allowed_user_ids:
            text = "Доступ ограничен."
            send_result = await self._sender.send_message(request.telegram_chat_id, text)
            return {"status": "forbidden", "reply": text, "send_result": send_result}

        async with self._store.user_lock(request.telegram_user_id):
            return await self._handle_message_locked(request)

    async def _handle_message_locked(self, request: TelegramExecutionRequest) -> dict[str, Any]:
        convo = await self._store.get_or_create(request.telegram_user_id, request.telegram_chat_id)
        snapshot = await self._sessions.resolve(request.telegram_user_id)
        convo.workspace_id = snapshot.get("workspace_id")
        convo.session_id = snapshot.get("active_session_id")
        await self._store.save(convo)

        await self._append_history(snapshot, role="user", content=request.user_input)

        if convo.flow_mode == FlowMode.RUNNING:
            text = "Ещё работаю над предыдущим запросом. Подождите немного."
            send_result = await self._sender.send_message(
                request.telegram_chat_id,
                text,
                reply_to_message_id=request.telegram_message_id,
            )
            return {
                "status": "busy",
                "reply": text,
                "workspace_id": convo.workspace_id,
                "send_result": send_result,
            }

        if convo.flow_mode == FlowMode.REVISION_PROMPTED:
            return await self._handle_revision_feedback(request, convo, snapshot)

        if convo.pending_clarification is not None:
            return await self._resume_pending_clarification(request, convo, snapshot)

        classification = await self._classify_intent(request, snapshot)

        # After a completed deliverable, route only via Executive — no keyword revision gate.
        if convo.flow_mode == FlowMode.COMPLETED:
            return await self._handle_after_completed(request, convo, snapshot, classification)

        if classification is not None:
            if is_chat_decision(classification.decision.action.value):
                return await self._handle_chat_response(request, convo, classification, snapshot)
            if is_task_decision(classification.decision.action.value):
                return await self._run_execution(
                    request, convo, snapshot, classification=classification
                )

        return await self._degraded_intent_reply(request, snapshot, convo)

    async def _handle_after_completed(
        self,
        request: TelegramExecutionRequest,
        convo: ConversationState,
        snapshot: dict[str, Any],
        classification,
    ) -> dict[str, Any]:
        if classification is None:
            return await self._degraded_intent_reply(request, snapshot, convo)

        if is_chat_decision(classification.decision.action.value):
            return await self._handle_chat_response(request, convo, classification, snapshot)

        if is_task_decision(classification.decision.action.value):
            caps = list(classification.understanding.required_capabilities or [])
            non_revision = [name for name in caps if name != "document_revision"]
            if non_revision:
                return await self._run_execution(
                    request, convo, snapshot, classification=classification
                )
            return await self._handle_revision_feedback(
                request, convo, snapshot, contextual=True
            )

        return await self._degraded_intent_reply(request, snapshot, convo)

    async def _degraded_intent_reply(
        self,
        request: TelegramExecutionRequest,
        snapshot: dict[str, Any],
        convo: ConversationState,
    ) -> dict[str, Any]:
        text = (
            "Сейчас не удалось определить намерение. "
            "Опишите задачу ещё раз или задайте вопрос текстом."
        )
        await self._append_history(snapshot, role="assistant", content=text)
        send_result = await self._sender.send_message(
            request.telegram_chat_id,
            text,
            reply_to_message_id=request.telegram_message_id,
        )
        return {
            "status": "completed",
            "intent": "degraded",
            "reply": text,
            "workspace_id": convo.workspace_id,
            "send_result": send_result,
        }

    async def _classify_intent(
        self,
        request: TelegramExecutionRequest,
        snapshot: dict[str, Any],
        *,
        pending: PendingClarification | None = None,
    ):
        if self._executive_agent is None:
            return None
        context, metadata = self._build_runtime_payload(request, snapshot, pending=pending)
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
        convo: ConversationState,
        classification,
        snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        action = classification.decision.action.value
        if action == "ASK_CLARIFICATION":
            convo.flow_mode = FlowMode.PENDING_CLARIFICATION
            convo.pending_clarification = build_pending_clarification(
                user_input=request.user_input,
                classification=classification,
            )
            convo.last_user_input = request.user_input
            # Keep prior artifact/revision context when clarifying a new task.
            await self._store.save(convo)

            text = extract_chat_reply(classification.decision.model_dump(mode="json")) or (
                "Уточните, пожалуйста, детали задачи."
            )
            if snapshot is not None:
                await self._append_history(snapshot, role="assistant", content=text)
            send_result = await self._sender.send_message(
                request.telegram_chat_id,
                text,
                reply_to_message_id=request.telegram_message_id,
            )
            return {
                "status": "clarification",
                "intent": "chat",
                "reply": text,
                "decision": classification.decision.model_dump(mode="json"),
                "workspace_id": convo.workspace_id,
                "send_result": send_result,
            }

        # RESPOND: do not wipe last_agent_state / artifacts — keep continuous dialogue + revision.
        convo.pending_clarification = None
        convo.last_user_input = request.user_input
        if convo.last_agent_state:
            convo.flow_mode = FlowMode.COMPLETED
        else:
            convo.flow_mode = FlowMode.IDLE
        await self._store.save(convo)

        text = extract_chat_reply(classification.decision.model_dump(mode="json")) or (
            "Не удалось сформулировать ответ. Повторите запрос, пожалуйста."
        )
        if snapshot is not None:
            await self._append_history(snapshot, role="assistant", content=text)
        send_result = await self._sender.send_message(
            request.telegram_chat_id,
            text,
            reply_to_message_id=request.telegram_message_id,
        )
        return {
            "status": "completed",
            "intent": "chat",
            "reply": text,
            "decision": classification.decision.model_dump(mode="json"),
            "workspace_id": convo.workspace_id,
            "send_result": send_result,
        }

    async def _resume_pending_clarification(
        self,
        request: TelegramExecutionRequest,
        convo: ConversationState,
        snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        pending = convo.pending_clarification
        if pending is None:
            return await self._run_execution(request, convo, snapshot)

        # Re-evaluate intent via Executive — never auto-execute on unclear classification.
        classification = await self._classify_intent(request, snapshot, pending=pending)
        if classification is not None and is_respond(classification.decision.action.value):
            convo.pending_clarification = None
            convo.flow_mode = FlowMode.IDLE
            await self._store.save(convo)
            return await self._handle_chat_response(request, convo, classification, snapshot)

        if classification is not None and is_clarification(classification.decision.action.value):
            return await self._handle_chat_response(request, convo, classification, snapshot)

        if classification is not None and is_task_decision(classification.decision.action.value):
            merged_input = merge_clarification_answer(pending, request.user_input)
            convo.pending_clarification = None
            convo.flow_mode = FlowMode.IDLE
            await self._store.save(convo)
            merged_request = request.model_copy(update={"user_input": merged_input})
            result = await self._run_execution(
                merged_request, convo, snapshot, classification=classification
            )
            result["resumed_from_clarification"] = True
            result["merged_input"] = merged_input
            return result

        # None or unexpected action: keep pending and ask again.
        missing = ", ".join(item for item in pending.missing_information if item)
        text = (
            f"Уточните, пожалуйста: {missing}."
            if missing
            else "Уточните, пожалуйста, детали задачи."
        )
        convo.flow_mode = FlowMode.PENDING_CLARIFICATION
        await self._store.save(convo)
        await self._append_history(snapshot, role="assistant", content=text)
        send_result = await self._sender.send_message(
            request.telegram_chat_id,
            text,
            reply_to_message_id=request.telegram_message_id,
        )
        return {
            "status": "clarification",
            "intent": "chat",
            "reply": text,
            "workspace_id": convo.workspace_id,
            "send_result": send_result,
            "pending_kept": True,
        }

    async def handle_callback(self, request: TelegramCallbackRequest) -> dict[str, Any]:
        if self._allowed_user_ids and request.telegram_user_id not in self._allowed_user_ids:
            text = "Доступ ограничен."
            send_result = await self._sender.send_message(request.telegram_chat_id, text)
            return {"status": "forbidden", "reply": text, "send_result": send_result}

        async with self._store.user_lock(request.telegram_user_id):
            return await self._handle_callback_locked(request)

    async def _handle_callback_locked(self, request: TelegramCallbackRequest) -> dict[str, Any]:
        convo = await self._store.get_or_create(request.telegram_user_id, request.telegram_chat_id)
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
        convo: ConversationState,
        snapshot: dict[str, Any],
        *,
        classification=None,
    ) -> dict[str, Any]:
        context, metadata = self._build_runtime_payload(request, snapshot)
        if classification is not None:
            metadata["preclassified_decision"] = classification.decision.model_dump(mode="json")
            metadata["preclassified_understanding"] = classification.understanding.model_dump(
                mode="json"
            )
            metadata["skip_executive_llm"] = True
        convo.flow_mode = FlowMode.RUNNING
        convo.last_user_input = request.user_input
        await self._store.save(convo)

        progress_message_id = await self._progress.start(
            request.telegram_chat_id,
            reply_to_message_id=request.telegram_message_id,
        )
        convo.progress_message_id = progress_message_id
        await self._store.save(convo)

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
        convo: ConversationState,
        progress_message_id: int | None,
        exc: GraphExecutionError,
    ) -> dict[str, Any]:
        convo.flow_mode = FlowMode.FAILED
        await self._store.save(convo)

        reason = _safe_error_reason(str(exc))
        text = format_runtime_error_message(
            trace_id=getattr(exc, "trace_id", None),
            execution_id=getattr(exc, "execution_id", None),
            reason=reason,
        )
        markup = retry_keyboard()
        replaced = await self._progress.replace(
            request.telegram_chat_id,
            progress_message_id,
            text,
            reply_markup=markup,
        )
        if replaced is not None:
            send_result = replaced
        else:
            send_result = await self._sender.send_message(
                request.telegram_chat_id,
                text,
                reply_markup=markup,
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
        convo: ConversationState,
        state: dict[str, Any],
        progress_message_id: int | None,
    ) -> dict[str, Any]:
        convo.last_execution_id = state.get("execution_id")
        convo.last_agent_state = state
        status = str(state.get("status") or "")

        if status == "waiting_approval":
            await self._progress.clear(request.telegram_chat_id, progress_message_id)
            convo.flow_mode = FlowMode.WAITING_APPROVAL
            await self._store.save(convo)
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
            convo.flow_mode = FlowMode.FAILED
            await self._store.save(convo)
            reason = extract_failure_reason(state)
            text = format_error_message(reason)
            markup = retry_keyboard()
            replaced = await self._progress.replace(
                request.telegram_chat_id,
                progress_message_id,
                text,
                reply_markup=markup,
            )
            if replaced is not None:
                send_result = replaced
            else:
                await self._progress.clear(request.telegram_chat_id, progress_message_id)
                send_result = await self._sender.send_message(
                    request.telegram_chat_id,
                    text,
                    reply_markup=markup,
                )
            return {
                "execution_id": state.get("execution_id"),
                "status": status,
                "reply": text,
                "send_result": send_result,
            }

        await self._progress.clear(request.telegram_chat_id, progress_message_id)

        artifacts = await self._artifacts.collect_artifacts(state)
        has_result = has_real_result_message(state)
        if status == "completed" and not artifacts and not has_result:
            convo.flow_mode = FlowMode.FAILED
            await self._store.save(convo)
            text = format_error_message(INCOMPLETE_REASON)
            markup = retry_keyboard()
            send_result = await self._sender.send_message(
                request.telegram_chat_id,
                text,
                reply_markup=markup,
            )
            await self._append_history(
                {"active_session_id": convo.session_id, "workspace_id": convo.workspace_id},
                role="assistant",
                content=text,
            )
            return {
                "execution_id": state.get("execution_id"),
                "status": "incomplete",
                "reply": text,
                "send_result": send_result,
                "progress_message_id": progress_message_id,
            }

        convo.flow_mode = FlowMode.COMPLETED
        convo.artifact_ids = [str(item.get("id")) for item in artifacts if item.get("id")]
        await self._store.save(convo)

        await self._set_active_artifact(convo, convo.artifact_ids[-1] if convo.artifact_ids else None)

        if artifacts:
            caption = format_delivery_caption(artifacts)
            await self._send_artifact_files(request.telegram_chat_id, artifacts, caption=caption)
            reply = format_delivery_summary(artifacts, state)
            send_result = {"ok": True, "via": "document_caption", "reply": reply}
        else:
            completion = format_completion_message(state)
            text = completion if status == "completed" else (
                self._mapper.extract_reply_text(state) or completion
            )
            send_result = await self._sender.send_message(request.telegram_chat_id, text)
            reply = text

        snapshot = {
            "active_session_id": convo.session_id,
            "workspace_id": convo.workspace_id,
        }
        await self._append_history(snapshot, role="assistant", content=str(reply))

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
        convo: ConversationState,
        snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        if convo.flow_mode != FlowMode.WAITING_APPROVAL or not convo.last_user_input:
            text = "Сейчас нет плана, ожидающего подтверждения."
            send_result = await self._sender.send_message(convo.telegram_chat_id, text)
            return {"status": "noop", "reply": text, "send_result": send_result}

        prior = convo.last_agent_state or {}
        metadata: dict[str, Any] = {
            "auto_approve": True,
            "source": "telegram",
            "skip_executive_llm": True,
        }
        # Resume from stored decision/plan — do not re-run Executive classification.
        if isinstance(prior.get("decision"), dict):
            metadata["preclassified_decision"] = prior["decision"]
        if isinstance(prior.get("understanding"), dict):
            metadata["preclassified_understanding"] = prior["understanding"]
        if isinstance(prior.get("task_plan"), dict):
            metadata["resume_task_plan"] = prior["task_plan"]

        request = TelegramExecutionRequest(
            user_input=convo.last_user_input,
            telegram_user_id=convo.telegram_user_id,
            telegram_chat_id=convo.telegram_chat_id,
            metadata=metadata,
            context={"channel": "telegram"},
        )
        return await self._run_execution(request, convo, snapshot)

    async def _handle_cancel(
        self,
        convo: ConversationState,
        request: TelegramCallbackRequest,
    ) -> dict[str, Any]:
        if convo.last_execution_id:
            self._orchestrator.cancel_execution(convo.last_execution_id)
        convo.flow_mode = FlowMode.CANCELLED
        await self._store.save(convo)
        text = "Выполнение отменено."
        send_result = await self._sender.send_message(convo.telegram_chat_id, text)
        return {"status": "cancelled", "reply": text, "send_result": send_result}

    async def _handle_revise_prompt(
        self,
        convo: ConversationState,
        request: TelegramCallbackRequest,
    ) -> dict[str, Any]:
        from datetime import datetime

        convo.flow_mode = FlowMode.REVISION_PROMPTED
        convo.revision_prompted_at = datetime.now()
        await self._store.save(convo)
        text = format_revision_prompt()
        send_result = await self._sender.send_message(convo.telegram_chat_id, text)
        return {"status": "revision_prompted", "reply": text, "send_result": send_result}

    async def _handle_revision_feedback(
        self,
        request: TelegramExecutionRequest,
        convo: ConversationState,
        snapshot: dict[str, Any],
        *,
        contextual: bool = False,
    ) -> dict[str, Any]:
        if not convo.last_agent_state or self._continuation is None:
            text = "Сначала нужно получить результат, прежде чем вносить правки."
            send_result = await self._sender.send_message(request.telegram_chat_id, text)
            return {"status": "revision_unavailable", "reply": text, "send_result": send_result}

        prior_state = self._enrich_prior_state_for_revision(convo)
        try:
            state = await self._continuation.continue_revision(
                prior_state,
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
        convo.flow_mode = FlowMode.COMPLETED
        convo.revision_prompted_at = None
        artifacts = await self._artifacts.collect_artifacts(state)
        convo.artifact_ids = [str(item.get("id")) for item in artifacts if item.get("id")] or list(
            convo.artifact_ids
        )
        await self._store.save(convo)

        await self._set_active_artifact(convo, convo.artifact_ids[-1] if convo.artifact_ids else None)

        if artifacts:
            caption = format_delivery_caption(artifacts)
            await self._send_artifact_files(request.telegram_chat_id, artifacts, caption=caption)
            reply = format_delivery_summary(artifacts, state)
            send_result = {"ok": True, "via": "document_caption", "reply": reply}
        else:
            reply = format_completion_message(state)
            send_result = await self._sender.send_message(request.telegram_chat_id, reply)

        await self._append_history(snapshot, role="assistant", content=str(reply))
        return {
            "status": "revised",
            "contextual": contextual,
            "reply": reply,
            "send_result": send_result,
        }

    async def _handle_retry(
        self,
        convo: ConversationState,
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

    async def _send_artifact_files(
        self,
        chat_id: int,
        artifacts: list[dict[str, Any]],
        *,
        caption: str | None = None,
    ) -> None:
        last_index = len(artifacts) - 1
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
            except Exception:
                continue

    def _build_runtime_payload(
        self,
        request: TelegramExecutionRequest,
        snapshot: dict[str, Any],
        *,
        pending: PendingClarification | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        context = {
            **request.context,
            "client_id": snapshot["client_id"],
            "workspace_id": snapshot["workspace_id"],
            "project_id": snapshot.get("active_project_id"),
            "channel": "telegram",
        }
        conversation = snapshot.get("conversation") or {}
        if conversation.get("messages"):
            context["conversation_history"] = list(conversation["messages"])
        if pending is not None:
            context["pending_clarification"] = pending.model_dump(mode="json")
            context["conversation_note"] = (
                "There is a pending clarification for a previous task. "
                "If the user is answering that clarification, continue the original task. "
                "If the user changed the topic to casual chat, RESPOND. "
                "If the user started a different deliverable, treat it as a new task."
            )
        metadata = {
            **request.metadata,
            "client_id": snapshot["client_id"],
            "workspace_id": snapshot["workspace_id"],
            "session_id": snapshot.get("active_session_id"),
            "source": "telegram",
        }
        if snapshot.get("active_artifact_id"):
            metadata["active_artifact_id"] = snapshot["active_artifact_id"]
            context["active_artifact_id"] = snapshot["active_artifact_id"]
        return context, metadata

    @staticmethod
    def _enrich_prior_state_for_revision(convo: ConversationState) -> dict[str, Any]:
        prior = dict(convo.last_agent_state or {})
        render_result = dict(prior.get("render_result") or {})
        if not render_result.get("artifact_id") and convo.artifact_ids:
            render_result["artifact_id"] = convo.artifact_ids[-1]
            prior["render_result"] = render_result
        metadata = dict(prior.get("metadata") or {})
        if convo.session_id and not metadata.get("session_id"):
            metadata["session_id"] = convo.session_id
        if convo.workspace_id and not metadata.get("workspace_id"):
            metadata["workspace_id"] = convo.workspace_id
        prior["metadata"] = metadata
        return prior

    async def _set_active_artifact(self, convo: ConversationState, artifact_id: str | None) -> None:
        if not artifact_id or not convo.workspace_id:
            return
        try:
            await self._sessions.workspace_manager.set_active_artifact(
                UUID(str(convo.workspace_id)),
                UUID(str(artifact_id)),
            )
        except Exception:
            return

    async def _append_history(self, snapshot: dict[str, Any], *, role: str, content: str) -> None:
        conversation = snapshot.get("conversation") or {}
        conversation_id = conversation.get("id")
        session_id = snapshot.get("active_session_id")
        if not conversation_id and session_id:
            try:
                ensured = await self._sessions.workspace_manager.ensure_conversation(UUID(str(session_id)))
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


INCOMPLETE_REASON = "Нет артефакта и нет текста результата."
