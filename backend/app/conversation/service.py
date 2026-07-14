from typing import Any
import uuid
from dataclasses import dataclass

from app.agent_runtime.exceptions import GraphExecutionError
from app.agent_runtime.runtime import AgentRuntime
from app.agent_runtime.state.models import create_initial_state
from app.agents.decision.policy import is_clarification, is_respond
from app.agents.executive.agent import ExecutiveAgent
from app.agents.intent.policy import extract_chat_reply, is_chat_decision, is_task_decision
from app.conversation.clarification import build_pending_clarification, merge_clarification_answer
from app.conversation.commands import SlashCommand, parse_slash_command
from app.conversation.messages import (
    INCOMPLETE_REASON,
    extract_creation_missing_information,
    extract_failure_reason,
    extract_reply_text,
    format_approval_message,
    format_completion_message,
    format_delivery_caption,
    format_working_header,
    format_delivery_summary,
    format_error_message,
    format_revision_prompt,
    format_runtime_error_message,
    format_slash_cancelled,
    format_slash_new_confirm,
    format_slash_nothing_to_cancel,
    format_slash_start,
    format_slash_status,
    has_real_result_message,
)
from app.conversation.models import ConversationState, FlowMode, PendingClarification
from app.conversation.ports import (
    ArtifactCollectorPort,
    ChannelNotifier,
    RevisionContinuationPort,
    SessionPort,
)
from app.conversation.requests import CallbackRequest, UserMessageRequest
from app.clients.resolver import BusinessClientResolver
from app.clients.work_summary import ClientWorkSummaryService
from app.memory.capture import DialogueMemoryCapture
from app.orchestration.orchestrator import Orchestrator


@dataclass
class _DeferredExecution:
    """Payload for long-running execute outside user_lock so /cancel can acquire it."""

    request: UserMessageRequest
    context: dict[str, Any]
    metadata: dict[str, Any]
    progress_message_id: int | None
    result_extras: dict[str, Any] | None = None


class ConversationService:
    """Channel-neutral product UX over existing runtime, orchestrator, and revision nodes."""

    def __init__(
        self,
        *,
        runtime: AgentRuntime,
        store,
        sessions: SessionPort,
        notifier: ChannelNotifier,
        artifacts: ArtifactCollectorPort,
        continuation: RevisionContinuationPort | None = None,
        orchestrator: Orchestrator | None = None,
        executive_agent: ExecutiveAgent | None = None,
        allowed_user_ids: set[int] | None = None,
        business_client_resolver: BusinessClientResolver | None = None,
        memory_capture: DialogueMemoryCapture | None = None,
        client_work_summary: ClientWorkSummaryService | None = None,
    ) -> None:
        self._runtime = runtime
        self._store = store
        self._sessions = sessions
        self._notifier = notifier
        self._artifacts = artifacts
        self._continuation = continuation
        self._orchestrator = orchestrator or Orchestrator()
        self._executive_agent = executive_agent
        # None = no filter (dev); empty set = deny all; non-empty = allowlist.
        self._allowed_user_ids = allowed_user_ids
        self._business_client_resolver = business_client_resolver
        self._memory_capture = memory_capture
        self._client_work_summary = client_work_summary

    def _user_allowed(self, user_id: int) -> bool:
        if self._allowed_user_ids is None:
            return True
        return user_id in self._allowed_user_ids

    async def handle_message(self, request: UserMessageRequest) -> dict[str, Any]:
        if not self._user_allowed(request.user_id):
            text = "Доступ ограничен."
            send_result = await self._notifier.send_text(request.chat_id, text)
            return {"status": "forbidden", "reply": text, "send_result": send_result}

        deferred: _DeferredExecution | None = None
        async with self._store.user_lock(request.user_id):
            result = await self._handle_message_locked(request)
            if isinstance(result, _DeferredExecution):
                deferred = result
            else:
                return result
        return await self._run_deferred_execution(deferred)

    async def _handle_message_locked(
        self, request: UserMessageRequest
    ) -> dict[str, Any] | _DeferredExecution:
        convo = await self._store.get_or_create(request.user_id, request.chat_id)
        snapshot = await self._sessions.resolve(request.user_id)
        convo.workspace_id = snapshot.get("workspace_id")
        convo.session_id = snapshot.get("active_session_id")
        await self._store.save(convo)

        await self._sessions.append_history(snapshot, role="user", content=request.text)

        # P1-I: release DB session after short persistence before LLM/classify.
        await self._sessions.release_db()

        command = parse_slash_command(request.text)
        if command is not None:
            return await self._handle_slash_command(command, request, convo, snapshot)

        if convo.flow_mode == FlowMode.RUNNING:
            text = "Ещё работаю над предыдущим запросом. Подождите немного."
            send_result = await self._notifier.send_text(
                request.chat_id,
                text,
                reply_to_message_id=request.message_id,
            )
            return {
                "status": "busy",
                "reply": text,
                "workspace_id": convo.workspace_id,
                "send_result": send_result,
            }

        if convo.pending_clarification is not None:
            return await self._resume_pending_clarification(request, convo, snapshot)

        classification = await self._classify_intent(request, snapshot, convo=convo)

        # After deliverable or revise prompt: Product Decision only (DecisionType).
        # Never branch on capability names (revision vs new task).
        if convo.flow_mode in {FlowMode.COMPLETED, FlowMode.REVISION_PROMPTED}:
            return await self._handle_after_completed(request, convo, snapshot, classification)

        if classification is not None:
            if is_chat_decision(classification.decision.action.value):
                return await self._handle_chat_response(request, convo, classification, snapshot)
            if is_task_decision(classification.decision.action.value):
                # Client/project bootstrap only after Executive chose a task.
                await self._attach_business_client(request.text, convo, snapshot)
                return await self._run_execution(
                    request, convo, snapshot, classification=classification
                )

        return await self._degraded_intent_reply(request, snapshot, convo)

    async def _handle_after_completed(
        self,
        request: UserMessageRequest,
        convo: ConversationState,
        snapshot: dict[str, Any],
        classification,
    ) -> dict[str, Any] | _DeferredExecution:
        """Route post-artifact / revision-prompt messages by DecisionType only."""
        if classification is None:
            return await self._degraded_intent_reply(request, snapshot, convo)

        if is_chat_decision(classification.decision.action.value):
            if convo.flow_mode == FlowMode.REVISION_PROMPTED:
                convo.flow_mode = (
                    FlowMode.COMPLETED if convo.last_agent_state else FlowMode.IDLE
                )
                convo.revision_prompted_at = None
                await self._store.save(convo)
            return await self._handle_chat_response(request, convo, classification, snapshot)

        if is_task_decision(classification.decision.action.value):
            # Capability graph (incl. revision vs creation) is owned by Resolver / runtime.
            if convo.flow_mode == FlowMode.REVISION_PROMPTED:
                convo.revision_prompted_at = None
                await self._store.save(convo)
            await self._attach_business_client(request.text, convo, snapshot)
            return await self._run_execution(
                request, convo, snapshot, classification=classification
            )

        return await self._degraded_intent_reply(request, snapshot, convo)

    async def _degraded_intent_reply(
        self,
        request: UserMessageRequest,
        snapshot: dict[str, Any],
        convo: ConversationState,
    ) -> dict[str, Any]:
        text = (
            "Сейчас не удалось определить намерение. "
            "Опишите задачу ещё раз или задайте вопрос текстом."
        )
        await self._sessions.append_history(snapshot, role="assistant", content=text)
        send_result = await self._notifier.send_text(
            request.chat_id,
            text,
            reply_to_message_id=request.message_id,
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
        request: UserMessageRequest,
        snapshot: dict[str, Any],
        *,
        pending: PendingClarification | None = None,
        convo: ConversationState | None = None,
    ):
        if self._executive_agent is None:
            return None
        context, metadata = self._build_runtime_payload(
            request, snapshot, pending=pending, convo=convo
        )
        state = create_initial_state(
            execution_id=uuid.uuid4().hex,
            trace_id=uuid.uuid4().hex[:16],
            user_input=request.text,
            context=context,
            metadata={**metadata, "intent_classification": True},
        )
        return await self._executive_agent.analyze(state)

    async def _handle_chat_response(
        self,
        request: UserMessageRequest,
        convo: ConversationState,
        classification,
        snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        action = classification.decision.action.value
        if action == "ASK_CLARIFICATION":
            convo.flow_mode = FlowMode.PENDING_CLARIFICATION
            convo.pending_clarification = build_pending_clarification(
                user_input=request.text,
                classification=classification,
            )
            convo.last_user_input = request.text
            # Keep prior artifact/revision context when clarifying a new task.
            await self._store.save(convo)

            text = extract_chat_reply(classification.decision.model_dump(mode="json")) or (
                "Уточните, пожалуйста, детали задачи."
            )
            if snapshot is not None:
                await self._sessions.append_history(snapshot, role="assistant", content=text)
            send_result = await self._notifier.send_text(
                request.chat_id,
                text,
                reply_to_message_id=request.message_id,
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
        convo.last_user_input = request.text
        if convo.last_agent_state:
            convo.flow_mode = FlowMode.COMPLETED
        else:
            convo.flow_mode = FlowMode.IDLE
        await self._store.save(convo)

        text = extract_chat_reply(classification.decision.model_dump(mode="json")) or (
            "Не удалось сформулировать ответ. Повторите запрос, пожалуйста."
        )
        if snapshot is not None:
            await self._sessions.append_history(snapshot, role="assistant", content=text)
        send_result = await self._notifier.send_text(
            request.chat_id,
            text,
            reply_to_message_id=request.message_id,
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
        request: UserMessageRequest,
        convo: ConversationState,
        snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        pending = convo.pending_clarification
        if pending is None:
            return await self._run_execution(request, convo, snapshot)

        # Re-evaluate intent via Executive — never auto-execute on unclear classification.
        classification = await self._classify_intent(
            request, snapshot, pending=pending, convo=convo
        )
        if classification is not None and is_respond(classification.decision.action.value):
            convo.pending_clarification = None
            convo.flow_mode = FlowMode.IDLE
            await self._store.save(convo)
            return await self._handle_chat_response(request, convo, classification, snapshot)

        if classification is not None and is_clarification(classification.decision.action.value):
            return await self._handle_chat_response(request, convo, classification, snapshot)

        if classification is not None and is_task_decision(classification.decision.action.value):
            merged_input = merge_clarification_answer(pending, request.text)
            convo.pending_clarification = None
            convo.flow_mode = FlowMode.IDLE
            await self._store.save(convo)
            merged_request = request.model_copy(update={"text": merged_input})
            await self._attach_business_client(merged_input, convo, snapshot)
            deferred = await self._run_execution(
                merged_request, convo, snapshot, classification=classification
            )
            deferred.result_extras = {
                "resumed_from_clarification": True,
                "merged_input": merged_input,
            }
            return deferred

        # None or unexpected action: keep pending and ask again.
        missing = ", ".join(item for item in pending.missing_information if item)
        text = (
            f"Уточните, пожалуйста: {missing}."
            if missing
            else "Уточните, пожалуйста, детали задачи."
        )
        convo.flow_mode = FlowMode.PENDING_CLARIFICATION
        await self._store.save(convo)
        await self._sessions.append_history(snapshot, role="assistant", content=text)
        send_result = await self._notifier.send_text(
            request.chat_id,
            text,
            reply_to_message_id=request.message_id,
        )
        return {
            "status": "clarification",
            "intent": "chat",
            "reply": text,
            "workspace_id": convo.workspace_id,
            "send_result": send_result,
            "pending_kept": True,
        }

    async def handle_callback(self, request: CallbackRequest) -> dict[str, Any]:
        if not self._user_allowed(request.user_id):
            text = "Доступ ограничен."
            send_result = await self._notifier.send_text(request.chat_id, text)
            return {"status": "forbidden", "reply": text, "send_result": send_result}

        deferred: _DeferredExecution | None = None
        async with self._store.user_lock(request.user_id):
            result = await self._handle_callback_locked(request)
            if isinstance(result, _DeferredExecution):
                deferred = result
            else:
                return result
        return await self._run_deferred_execution(deferred)

    async def _handle_callback_locked(
        self, request: CallbackRequest
    ) -> dict[str, Any] | _DeferredExecution:
        convo = await self._store.get_or_create(request.user_id, request.chat_id)
        snapshot = await self._sessions.resolve(request.user_id)
        await self._sessions.release_db()

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
        request: UserMessageRequest,
        convo: ConversationState,
        snapshot: dict[str, Any],
        *,
        classification=None,
    ) -> _DeferredExecution:
        context, metadata = self._build_runtime_payload(request, snapshot, convo=convo)
        if classification is not None:
            metadata["preclassified_decision"] = classification.decision.model_dump(mode="json")
            metadata["preclassified_understanding"] = classification.understanding.model_dump(
                mode="json"
            )
            metadata["skip_executive_llm"] = True
        convo.flow_mode = FlowMode.RUNNING
        convo.last_user_input = request.text
        await self._store.save(convo)

        progress_message_id: int | None = None
        if self._should_show_progress(classification, convo):
            header = self._progress_header(classification)
            progress_message_id = await self._notifier.start_progress(
                request.chat_id,
                reply_to_message_id=request.message_id,
                header=header,
            )
            convo.progress_message_id = progress_message_id
            await self._store.save(convo)

        return _DeferredExecution(
            request=request,
            context=context,
            metadata=metadata,
            progress_message_id=progress_message_id,
        )

    async def _run_deferred_execution(self, deferred: _DeferredExecution) -> dict[str, Any]:
        request = deferred.request
        progress_message_id = deferred.progress_message_id
        try:
            state = await self._execute_with_progress(
                request.text,
                chat_id=request.chat_id,
                progress_message_id=progress_message_id,
                context=deferred.context,
                metadata=deferred.metadata,
            )
        except GraphExecutionError as exc:
            async with self._store.user_lock(request.user_id):
                convo = await self._store.get_or_create(request.user_id, request.chat_id)
                if convo.flow_mode in {FlowMode.IDLE, FlowMode.CANCELLED}:
                    await self._notifier.clear_progress(request.chat_id, progress_message_id)
                    return {
                        "status": "cancelled",
                        "reply": format_slash_cancelled(),
                        "execution_id": convo.last_execution_id,
                    }
                return await self._handle_execution_failure(
                    request,
                    convo,
                    progress_message_id,
                    exc,
                )
        except Exception as exc:
            async with self._store.user_lock(request.user_id):
                convo = await self._store.get_or_create(request.user_id, request.chat_id)
                if convo.flow_mode in {FlowMode.IDLE, FlowMode.CANCELLED}:
                    await self._notifier.clear_progress(request.chat_id, progress_message_id)
                    return {
                        "status": "cancelled",
                        "reply": format_slash_cancelled(),
                        "execution_id": convo.last_execution_id,
                    }
                return await self._handle_execution_failure(
                    request,
                    convo,
                    progress_message_id,
                    GraphExecutionError(str(exc)),
                )

        state_dict = dict(state) if not isinstance(state, dict) else state
        async with self._store.user_lock(request.user_id):
            convo = await self._store.get_or_create(request.user_id, request.chat_id)
            if convo.flow_mode in {FlowMode.IDLE, FlowMode.CANCELLED}:
                await self._notifier.clear_progress(request.chat_id, progress_message_id)
                return {
                    "status": "cancelled",
                    "reply": format_slash_cancelled(),
                    "execution_id": state_dict.get("execution_id") or convo.last_execution_id,
                }
            result = await self._deliver_outcome(
                request, convo, state_dict, progress_message_id
            )
            if deferred.result_extras:
                result = {**result, **deferred.result_extras}
            return result

    @staticmethod
    def _should_show_progress(classification, convo: ConversationState) -> bool:
        """Show progress only for real multi-step work — no fake theater on simple EXECUTE.

        CREATE_PLAN (and approval resumes without a fresh classification) get live stages.
        Single-capability EXECUTE delivers quietly; chat never reaches this path.
        """
        _ = convo
        if classification is None:
            # Approval / retry resume — prior path already chose multi-step work.
            return True
        action = getattr(getattr(classification, "decision", None), "action", None)
        action_value = action.value if hasattr(action, "value") else str(action or "")
        if action_value == "CREATE_PLAN":
            return True
        understanding = getattr(classification, "understanding", None)
        caps = list(getattr(understanding, "required_capabilities", None) or [])
        # Multiple Executive hints imply multi-stage work worth staging in chat.
        return len([c for c in caps if c and str(c).strip()]) > 1

    @staticmethod
    def _progress_header(classification) -> str | None:
        goal: str | None = None
        if classification is not None:
            understanding = getattr(classification, "understanding", None)
            goal = getattr(understanding, "goal", None)
        return format_working_header(goal)

    async def _handle_execution_failure(
        self,
        request: UserMessageRequest,
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
        send_result = await self._notifier.send_retry(
            request.chat_id,
            text,
            progress_message_id=progress_message_id,
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
        # None means progress was intentionally skipped (single-step EXECUTE) — do not late-start.
        progress_enabled = progress_message_id is not None

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
                    if progress_enabled:
                        progress_message_id = await self._notifier.update_progress(
                            chat_id,
                            progress_message_id,
                            last_progress,
                        )
                final_state = self._merge_state(final_state, update)

        if final_state is not None:
            if progress_enabled:
                await self._notifier.finalize_progress(
                    chat_id, progress_message_id, last_progress
                )
            return final_state

        state = await self._runtime.execute(
            user_input,
            context=context,
            metadata=metadata,
        )
        state_dict = dict(state) if not isinstance(state, dict) else state
        if progress_enabled:
            await self._notifier.finalize_progress(
                chat_id, progress_message_id, state_dict.get("telegram_progress")
            )
        return state_dict

    async def _deliver_outcome(
        self,
        request: UserMessageRequest,
        convo: ConversationState,
        state: dict[str, Any],
        progress_message_id: int | None,
    ) -> dict[str, Any]:
        convo.last_execution_id = state.get("execution_id")
        convo.last_agent_state = state
        status = str(state.get("status") or "")

        if status == "waiting_approval":
            await self._notifier.clear_progress(request.chat_id, progress_message_id)
            convo.flow_mode = FlowMode.WAITING_APPROVAL
            await self._store.save(convo)
            text = format_approval_message(state.get("task_plan"))
            send_result = await self._notifier.send_approval(request.chat_id, text)
            return {
                "execution_id": state.get("execution_id"),
                "status": status,
                "reply": text,
                "send_result": send_result,
            }

        if status in {"execution_failed", "failed"} or status.endswith("_failed"):
            # Honesty first: never invent ASK_CLARIFICATION here. Only Executive may
            # choose that Product Decision on a subsequent user turn.
            convo.flow_mode = FlowMode.FAILED
            await self._store.save(convo)
            reason = extract_failure_reason(state)
            missing = extract_creation_missing_information(state)
            if missing and not reason:
                reason = "; ".join(missing)
            text = format_error_message(reason)
            send_result = await self._notifier.send_retry(
                request.chat_id,
                text,
                progress_message_id=progress_message_id,
            )
            return {
                "execution_id": state.get("execution_id"),
                "status": status,
                "reply": text,
                "send_result": send_result,
            }

        await self._notifier.clear_progress(request.chat_id, progress_message_id)

        artifacts = await self._artifacts.collect_artifacts(state)
        has_result = has_real_result_message(state)

        if status == "waiting_user_revision":
            if artifacts:
                convo.flow_mode = FlowMode.REVISION_PROMPTED
                convo.artifact_ids = [str(item.get("id")) for item in artifacts if item.get("id")]
                await self._store.save(convo)
                await self._set_active_artifact(
                    convo, convo.artifact_ids[-1] if convo.artifact_ids else None
                )
                caption = format_delivery_caption(artifacts)
                send_result = await self._notifier.send_artifacts(
                    request.chat_id, artifacts, caption=caption
                )
                prompt = format_revision_prompt()
                prompt_send = await self._notifier.send_text(request.chat_id, prompt)
                reply = prompt
                snapshot = {
                    "active_session_id": convo.session_id,
                    "workspace_id": convo.workspace_id,
                }
                await self._sessions.append_history(snapshot, role="assistant", content=reply)
                return {
                    "execution_id": state.get("execution_id"),
                    "trace_id": state.get("trace_id"),
                    "status": status,
                    "reply": reply,
                    "workspace_id": convo.workspace_id,
                    "send_result": {**send_result, "prompt": prompt_send},
                    "progress_message_id": progress_message_id,
                }

            convo.flow_mode = FlowMode.FAILED
            await self._store.save(convo)
            text = format_error_message(INCOMPLETE_REASON)
            send_result = await self._notifier.send_retry(request.chat_id, text)
            await self._sessions.append_history(
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

        if status == "completed" and not artifacts and not has_result:
            convo.flow_mode = FlowMode.FAILED
            await self._store.save(convo)
            text = format_error_message(INCOMPLETE_REASON)
            send_result = await self._notifier.send_retry(request.chat_id, text)
            await self._sessions.append_history(
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

        # Non-completed statuses without a real reply must not dump internal status/
        # understanding paraphrase into chat.
        if status != "completed" and not artifacts and not has_result:
            convo.flow_mode = FlowMode.FAILED
            await self._store.save(convo)
            text = format_error_message(INCOMPLETE_REASON)
            send_result = await self._notifier.send_retry(request.chat_id, text)
            await self._sessions.append_history(
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
            send_result = await self._notifier.send_artifacts(
                request.chat_id, artifacts, caption=caption
            )
            reply = format_delivery_summary(artifacts, state)
            send_result = {**send_result, "reply": reply}
        else:
            completion = format_completion_message(state)
            text = completion if has_result else (
                extract_reply_text(state) if status == "completed" else completion
            )
            if not has_result and (not text or text == status):
                text = format_error_message(INCOMPLETE_REASON)
            send_result = await self._notifier.send_text(request.chat_id, text)
            reply = text

        snapshot = {
            "active_session_id": convo.session_id,
            "workspace_id": convo.workspace_id,
        }
        await self._sessions.append_history(snapshot, role="assistant", content=str(reply))

        # Post-action memory hook only — never a pre-Executive keyword router.
        if self._memory_capture is not None and status == "completed":
            await self._memory_capture.persist_candidates(state.get("memory_candidates") or [])

        return {
            "execution_id": state.get("execution_id"),
            "trace_id": state.get("trace_id"),
            "status": status,
            "reply": reply,
            "workspace_id": convo.workspace_id,
            "send_result": send_result,
            "progress_message_id": progress_message_id,
        }

    async def _attach_business_client(
        self,
        text: str,
        convo: ConversationState,
        snapshot: dict[str, Any],
    ) -> None:
        if self._business_client_resolver is None:
            return
        resolved = await self._business_client_resolver.resolve(
            text,
            trace_id=str(snapshot.get("workspace_id") or "-"),
        )
        if resolved is None:
            return
        convo.business_client_id = str(resolved.client_id)
        convo.business_client_name = resolved.name
        if resolved.project_id is not None:
            convo.business_project_id = str(resolved.project_id)
        await self._store.save(convo)

    async def _handle_slash_command(
        self,
        command: SlashCommand,
        request: UserMessageRequest,
        convo: ConversationState,
        snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        if command == SlashCommand.START:
            text = format_slash_start()
            await self._sessions.append_history(snapshot, role="assistant", content=text)
            send_result = await self._notifier.send_text(
                request.chat_id,
                text,
                reply_to_message_id=request.message_id,
            )
            return {"status": "command", "command": "start", "reply": text, "send_result": send_result}

        if command == SlashCommand.STATUS:
            text = format_slash_status(convo)
            send_result = await self._notifier.send_text(
                request.chat_id,
                text,
                reply_to_message_id=request.message_id,
            )
            return {"status": "command", "command": "status", "reply": text, "send_result": send_result}

        if command == SlashCommand.NEW:
            await self._notifier.clear_progress(request.chat_id, convo.progress_message_id)
            await self._store.reset_dialog(request.user_id)
            text = format_slash_new_confirm()
            await self._sessions.append_history(snapshot, role="assistant", content=text)
            send_result = await self._notifier.send_text(
                request.chat_id,
                text,
                reply_to_message_id=request.message_id,
            )
            return {"status": "command", "command": "new", "reply": text, "send_result": send_result}

        if command == SlashCommand.CANCEL:
            return await self._handle_slash_cancel(request, convo)

        text = format_slash_start()
        send_result = await self._notifier.send_text(request.chat_id, text)
        return {"status": "command", "command": "unknown", "reply": text, "send_result": send_result}

    async def _handle_slash_cancel(
        self,
        request: UserMessageRequest,
        convo: ConversationState,
    ) -> dict[str, Any]:
        cancellable = {FlowMode.RUNNING, FlowMode.WAITING_APPROVAL}
        if convo.flow_mode not in cancellable:
            text = format_slash_nothing_to_cancel()
            send_result = await self._notifier.send_text(
                request.chat_id,
                text,
                reply_to_message_id=request.message_id,
            )
            return {
                "status": "command",
                "command": "cancel",
                "reply": text,
                "send_result": send_result,
            }

        if convo.last_execution_id:
            self._orchestrator.cancel_execution(convo.last_execution_id)
        await self._notifier.clear_progress(request.chat_id, convo.progress_message_id)
        convo.flow_mode = FlowMode.IDLE
        convo.progress_message_id = None
        await self._store.save(convo)
        text = format_slash_cancelled()
        send_result = await self._notifier.send_text(
            request.chat_id,
            text,
            reply_to_message_id=request.message_id,
        )
        return {
            "status": "cancelled",
            "command": "cancel",
            "reply": text,
            "send_result": send_result,
        }

    async def _handle_approval_resume(
        self,
        convo: ConversationState,
        snapshot: dict[str, Any],
    ) -> dict[str, Any] | _DeferredExecution:
        if convo.flow_mode != FlowMode.WAITING_APPROVAL or not convo.last_user_input:
            text = "Сейчас нечего подтверждать — опишите задачу текстом."
            send_result = await self._notifier.send_text(convo.chat_id, text)
            return {"status": "noop", "reply": text, "send_result": send_result}

        prior = convo.last_agent_state or {}
        metadata: dict[str, Any] = {
            "auto_approve": True,
            "skip_executive_llm": True,
        }
        # Resume from stored decision/plan — do not re-run Executive classification.
        if isinstance(prior.get("decision"), dict):
            metadata["preclassified_decision"] = prior["decision"]
        if isinstance(prior.get("understanding"), dict):
            metadata["preclassified_understanding"] = prior["understanding"]
        if isinstance(prior.get("task_plan"), dict):
            metadata["resume_task_plan"] = prior["task_plan"]

        channel = (snapshot.get("metadata") or {}).get("source") or "channel"
        request = UserMessageRequest(
            text=convo.last_user_input,
            user_id=convo.user_id,
            chat_id=convo.chat_id,
            metadata={**metadata, "source": channel},
            context={"channel": channel},
        )
        return await self._run_execution(request, convo, snapshot)

    async def _handle_cancel(
        self,
        convo: ConversationState,
        request: CallbackRequest,
    ) -> dict[str, Any]:
        if convo.last_execution_id:
            self._orchestrator.cancel_execution(convo.last_execution_id)
        await self._notifier.clear_progress(convo.chat_id, convo.progress_message_id)
        convo.flow_mode = FlowMode.CANCELLED
        convo.progress_message_id = None
        await self._store.save(convo)
        text = format_slash_cancelled()
        send_result = await self._notifier.send_text(convo.chat_id, text)
        return {"status": "cancelled", "reply": text, "send_result": send_result}

    async def _handle_revise_prompt(
        self,
        convo: ConversationState,
        request: CallbackRequest,
    ) -> dict[str, Any]:
        from datetime import datetime

        convo.flow_mode = FlowMode.REVISION_PROMPTED
        convo.revision_prompted_at = datetime.now()
        await self._store.save(convo)
        text = format_revision_prompt()
        send_result = await self._notifier.send_text(convo.chat_id, text)
        return {"status": "revision_prompted", "reply": text, "send_result": send_result}

    async def _handle_retry(
        self,
        convo: ConversationState,
        snapshot: dict[str, Any],
        request: CallbackRequest,
    ) -> dict[str, Any] | _DeferredExecution:
        if not convo.last_user_input:
            text = "Нечего повторить. Опишите задачу текстом."
            send_result = await self._notifier.send_text(convo.chat_id, text)
            return {"status": "noop", "reply": text, "send_result": send_result}

        channel = (request.metadata or {}).get("source") or "channel"
        exec_request = UserMessageRequest(
            text=convo.last_user_input,
            user_id=convo.user_id,
            chat_id=convo.chat_id,
            metadata={"source": channel, "retry": True},
            context={"channel": channel},
        )
        return await self._run_execution(exec_request, convo, snapshot)

    def _build_runtime_payload(
        self,
        request: UserMessageRequest,
        snapshot: dict[str, Any],
        *,
        pending: PendingClarification | None = None,
        convo: ConversationState | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        channel = request.context.get("channel") or request.metadata.get("source") or "channel"
        business_client_id = convo.business_client_id if convo is not None else None
        business_client_name = convo.business_client_name if convo is not None else None
        effective_client_id = business_client_id or snapshot["client_id"]
        business_project_id = convo.business_project_id if convo is not None else None
        effective_project_id = business_project_id or snapshot.get("active_project_id")
        context = {
            **request.context,
            "client_id": effective_client_id,
            "workspace_id": snapshot["workspace_id"],
            "project_id": effective_project_id,
            "channel": channel,
        }
        if business_client_id:
            context["business_client_id"] = business_client_id
        if business_client_name:
            context["client_name"] = business_client_name
            context["business_client_name"] = business_client_name
        conversation = snapshot.get("conversation") or {}
        if conversation.get("messages"):
            context["conversation_history"] = list(conversation["messages"])
        if pending is not None:
            # Facts only — no coaching rules that steer Product Decision.
            context["pending_clarification"] = pending.model_dump(mode="json")
        metadata = {
            **request.metadata,
            "client_id": effective_client_id,
            "workspace_id": snapshot["workspace_id"],
            "session_id": snapshot.get("active_session_id"),
            "source": request.metadata.get("source") or channel,
        }
        if snapshot.get("active_artifact_id"):
            metadata["active_artifact_id"] = snapshot["active_artifact_id"]
            context["active_artifact_id"] = snapshot["active_artifact_id"]
        return context, metadata

    async def _set_active_artifact(self, convo: ConversationState, artifact_id: str | None) -> None:
        if not artifact_id or not convo.workspace_id:
            return
        await self._sessions.set_active_artifact(convo.workspace_id, artifact_id)

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
