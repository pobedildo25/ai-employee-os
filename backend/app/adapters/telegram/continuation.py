from typing import Any
from uuid import UUID

from app.agent_runtime.state.models import AgentState
from app.quality.nodes.quality_gate_node import QualityGateNode
from app.revision.manager import RevisionManager
from app.revision.models import RevisionStatus
from app.revision.nodes.revision_node import RevisionNode
from app.revision.parsers.feedback_parser import build_revision_request_from_review
from app.services.artifact_service import ArtifactService
from app.services.artifact_service import ArtifactService
from app.skills.registry import CapabilityRegistry
from app.storage.storage_interface import StorageInterface


class TelegramGraphContinuation:
    """Resume existing graph nodes for Telegram revision without changing AgentRuntime."""

    def __init__(
        self,
        *,
        revision_node: RevisionNode | None = None,
        quality_gate_node: QualityGateNode | None = None,
        revision_manager: RevisionManager | None = None,
        capability_registry: CapabilityRegistry | None = None,
    ) -> None:
        self._revision_node = revision_node
        self._quality_gate_node = quality_gate_node
        self._revision_manager = revision_manager
        self._registry = capability_registry

    async def continue_revision(self, prior_state: dict[str, Any], user_feedback: str) -> dict[str, Any]:
        if self._revision_node is None or self._quality_gate_node is None:
            raise RuntimeError("Revision continuation is not configured")

        state: AgentState = dict(prior_state)
        metadata = dict(state.get("metadata") or {})
        metadata["user_feedback"] = user_feedback
        state["metadata"] = metadata

        revision_update = await self._revision_node(state)
        merged: dict[str, Any] = {**state, **revision_update}

        if merged.get("status") == "waiting_user_revision":
            merged = await self._apply_user_revision(merged, user_feedback)

        quality_update = await self._quality_gate_node(merged)
        return {**merged, **quality_update}

    async def _apply_user_revision(self, state: dict[str, Any], user_feedback: str) -> dict[str, Any]:
        if self._registry is not None:
            skill = self._registry.get_skill_for_capability("document_revision")
            if skill is not None:
                payload = {
                    "user_feedback": user_feedback,
                    "document_ast": state.get("document_ast"),
                    "revision_request": state.get("revision_request"),
                    "source_artifact_id": (state.get("render_result") or {}).get("artifact_id"),
                    "client_id": (state.get("metadata") or {}).get("client_id"),
                    "project_id": (state.get("context") or {}).get("project_id"),
                    "trace_id": state.get("trace_id", "-"),
                }
                skill_result = await skill.execute(payload)
                return {
                    **state,
                    "revision_result": skill_result.get("revision_result"),
                    "document_ast": (skill_result.get("revision_result") or {}).get("document_ast")
                    or state.get("document_ast"),
                    "status": "revised",
                }

        if self._revision_manager is None:
            return state

        request = build_revision_request_from_review(
            issues=(state.get("revision_request") or {}).get("issues")
            or (state.get("review_result") or {}).get("issues")
            or [],
            suggested_changes=(state.get("revision_request") or {}).get("suggested_changes") or [],
            source_artifact_id=(state.get("render_result") or {}).get("artifact_id"),
            user_feedback=user_feedback,
            revision_count=int(state.get("revision_count") or 0),
        )
        result = await self._revision_manager.apply_revision(
            request,
            document_ast=state.get("document_ast"),
            context=state.get("execution_context") or {},
            client_id=_to_uuid((state.get("metadata") or {}).get("client_id")),
            project_id=_to_uuid((state.get("context") or {}).get("project_id")),
            trace_id=state.get("trace_id", "-"),
        )
        return {
            **state,
            "revision_result": result.model_dump(mode="json"),
            "status": "revised" if result.status == RevisionStatus.COMPLETED else state.get("status"),
        }


def _to_uuid(value: Any) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        return None


class TelegramArtifactDelivery:
    """Send rendered artifacts to Telegram using existing ArtifactService + storage."""

    def __init__(
        self,
        artifact_service: ArtifactService | None,
        storage: StorageInterface | None,
    ) -> None:
        self._artifact_service = artifact_service
        self._storage = storage

    async def collect_artifacts(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        if self._artifact_service is None:
            return []

        artifact_ids: list[str] = []
        render = state.get("render_result") or {}
        revision = state.get("revision_result") or {}
        for raw_id in (revision.get("artifact_id"), render.get("artifact_id")):
            if raw_id and str(raw_id) not in artifact_ids:
                artifact_ids.append(str(raw_id))

        artifacts: list[dict[str, Any]] = []
        for raw_id in artifact_ids:
            try:
                artifact = await self._artifact_service.get_by_id(UUID(str(raw_id)))
            except (ValueError, TypeError):
                continue
            if artifact is None:
                continue
            artifacts.append(artifact.model_dump(mode="json"))
        return artifacts

    async def download(self, artifact: dict[str, Any]) -> bytes | None:
        if self._storage is None:
            return None
        path = artifact.get("storage_path")
        if not path:
            return None
        try:
            return await self._storage.download(str(path))
        except Exception:
            return None
