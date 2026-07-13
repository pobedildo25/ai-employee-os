from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING
from uuid import UUID

from app.agent_runtime.state.models import AgentState
from app.revision.manager import RevisionManager
from app.revision.memory_preparer import prepare_revision_memory_items
from app.revision.models import RevisionRequest, RevisionStatus
from app.revision.parsers.feedback_parser import build_revision_request_from_review
from app.revision.policies.revision_policy import can_auto_revise, next_revision_count

if TYPE_CHECKING:
    from app.learning.manager import LearningManager

logger = logging.getLogger(__name__)

REVISION_NODE = "revision"


class RevisionNode:
    name = REVISION_NODE

    def __init__(
        self,
        manager: RevisionManager,
        learning_manager: "LearningManager | None" = None,
    ) -> None:
        self._manager = manager
        self._learning_manager = learning_manager

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        _log_node(state, self.name, "started")

        revision_count = int(state.get("revision_count") or 0)
        review_result = state.get("review_result") or {}
        existing_request = state.get("revision_request") or {}
        metadata = state.get("metadata") or {}
        execution_context = state.get("execution_context") or {}

        user_feedback = metadata.get("user_feedback") or existing_request.get("user_feedback")

        request = build_revision_request_from_review(
            issues=existing_request.get("issues") or review_result.get("issues") or [],
            suggested_changes=existing_request.get("suggested_changes")
            or review_result.get("recommendations")
            or [],
            source_artifact_id=existing_request.get("source_artifact_id")
            or existing_request.get("source_artifact")
            or (state.get("render_result") or {}).get("artifact_id"),
            user_feedback=user_feedback,
            revision_count=revision_count,
            metadata={"from_quality_gate": True},
        )

        if not can_auto_revise(revision_count):
            waiting = request.model_copy(
                update={
                    "revision_count": revision_count,
                    "metadata": {**request.metadata, "waiting_user": True},
                }
            )
            update = {
                "current_step": self.name,
                "status": "waiting_user_revision",
                "revision_request": waiting.model_dump(mode="json"),
                "revision_result": {
                    "status": RevisionStatus.WAITING_USER.value,
                    "summary": "Automatic revision limit reached",
                    "changes_applied": [],
                    "artifact_id": waiting.source_artifact_id,
                },
                "revision_count": revision_count,
            }
            _log_node({**state, **update}, self.name, "waiting_user")
            return update

        brand_profile = execution_context.get("brand_profile") or state.get("context", {}).get(
            "brand_profile"
        )
        client_id = _to_uuid(
            execution_context.get("client_id")
            or state.get("context", {}).get("client_id")
            or metadata.get("client_id")
        )
        project_id = _to_uuid(
            execution_context.get("project_id")
            or state.get("context", {}).get("project_id")
            or metadata.get("project_id")
        )
        output_format = (
            ((state.get("document_creation_result") or {}).get("metadata") or {}).get("document_type")
            or "docx"
        )

        result = await self._manager.apply_revision(
            request,
            document_ast=state.get("document_ast"),
            context={
                **execution_context,
                "understanding": state.get("understanding") or {},
                "title": ((state.get("document_creation_result") or {}).get("metadata") or {}).get(
                    "title"
                ),
            },
            brand_profile=brand_profile,
            client_id=client_id,
            project_id=project_id,
            output_format=str(output_format),
            trace_id=state.get("trace_id", "-"),
        )

        new_count = next_revision_count(revision_count)
        memory_items = prepare_revision_memory_items(
            request.model_copy(update={"revision_count": new_count}),
            result,
            client_id=client_id,
            project_id=project_id,
            session_id=metadata.get("session_id"),
        )

        learning_result = None
        if self._learning_manager is not None and user_feedback:
            from app.learning.models import LearningSource
            from app.learning.policies.learning_policy import LearningPolicy

            # One-off document edits ("короче", …) are not durable preferences.
            policy = getattr(self._learning_manager, "_policy", None) or LearningPolicy()
            feedback_text = str(user_feedback)
            if not policy.looks_like_preference(feedback_text):
                logger.info(
                    "revision auto-learn skipped (not durable preference) | trace_id=%s",
                    state.get("trace_id", "-"),
                )
            else:
                try:
                    learned = await self._learning_manager.learn(
                        feedback_text,
                        source=LearningSource.REVISION_REQUEST,
                        client_id=client_id,
                        project_id=project_id,
                        context=execution_context,
                        trace_id=state.get("trace_id", "-"),
                    )
                    learning_result = learned.model_dump(mode="json") if learned else None
                except Exception as exc:
                    logger.warning(
                        "learning from revision skipped | trace_id=%s error=%s",
                        state.get("trace_id", "-"),
                        exc,
                    )

        render_meta = (result.metadata or {}).get("render_result") or {}
        update: dict[str, Any] = {
            "current_step": self.name,
            "status": "revised" if result.status == RevisionStatus.COMPLETED else result.status.value.lower(),
            "revision_request": request.model_copy(update={"revision_count": new_count}).model_dump(
                mode="json"
            ),
            "revision_result": result.model_dump(mode="json"),
            "revision_count": new_count,
            "document_ast": result.document_ast or state.get("document_ast"),
            "memory_candidates": [item.model_dump(mode="json") for item in memory_items],
            "learning_result": learning_result,
        }
        if render_meta:
            update["render_result"] = render_meta
        elif result.artifact_id:
            update["render_result"] = {
                **(state.get("render_result") or {}),
                "artifact_id": str(result.artifact_id),
                "metadata": {
                    **((state.get("render_result") or {}).get("metadata") or {}),
                    "version_id": result.version_id,
                    "revision_count": new_count,
                },
            }

        _log_node({**state, **update}, self.name, "completed")
        return update


def _log_node(state: AgentState, node_name: str, status: str) -> None:
    logger.info(
        "graph node execution | execution_id=%s trace_id=%s node_name=%s status=%s",
        state.get("execution_id", "-"),
        state.get("trace_id", "-"),
        node_name,
        status,
    )


def _to_uuid(value: object | None) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    return UUID(str(value))
