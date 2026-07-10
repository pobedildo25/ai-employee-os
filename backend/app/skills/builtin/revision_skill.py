from typing import Any
from uuid import UUID

from app.revision.manager import RevisionManager
from app.revision.memory_preparer import prepare_revision_memory_items
from app.revision.models import RevisionRequest
from app.revision.parsers.feedback_parser import build_revision_request_from_review
from app.skills.base.skill import BaseSkill
from app.skills.models import Capability, SkillMetadata


class RevisionSkill(BaseSkill):
    """Applies document revision based on quality feedback."""

    def __init__(self, manager: RevisionManager | None = None) -> None:
        if manager is None:
            from app.llm.gateway import create_llm_gateway
            from app.revision.agent import RevisionAgent

            manager = RevisionManager(RevisionAgent(create_llm_gateway()))
        self._manager = manager
        super().__init__(
            metadata=SkillMetadata(
                id="revision_skill",
                name="revision_skill",
                description="Ревизия документа по замечаниям Quality Gate и feedback пользователя",
                capabilities=["document_revision"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "revision_request": {"type": "object"},
                        "document_ast": {"type": "object"},
                        "user_feedback": {"type": "string"},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "revision_result": {"type": "object"},
                    },
                },
            ),
            capabilities=[
                Capability(
                    name="document_revision",
                    description="Улучшение документа на основе замечаний и feedback",
                    category="document",
                ),
            ],
        )

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw_request = payload.get("revision_request")
        if raw_request is None and not payload.get("issues") and not payload.get("user_feedback"):
            return {
                "status": "failed",
                "skill": self.name(),
                "message": "revision_request or feedback is required",
                "payload_keys": list(payload.keys()),
            }

        if isinstance(raw_request, RevisionRequest):
            request = raw_request
            if payload.get("user_feedback"):
                request = build_revision_request_from_review(
                    issues=request.issues,
                    suggested_changes=request.suggested_changes,
                    source_artifact_id=request.source_artifact_id,
                    user_feedback=payload.get("user_feedback"),
                    revision_count=request.revision_count,
                    metadata=request.metadata,
                )
        else:
            data = dict(raw_request or {})
            request = build_revision_request_from_review(
                issues=data.get("issues") or payload.get("issues") or [],
                suggested_changes=data.get("suggested_changes") or payload.get("suggested_changes") or [],
                source_artifact_id=data.get("source_artifact_id")
                or data.get("source_artifact")
                or payload.get("source_artifact_id"),
                user_feedback=payload.get("user_feedback") or data.get("user_feedback"),
                revision_count=int(data.get("revision_count") or payload.get("revision_count") or 0),
                metadata=data.get("metadata") or {},
            )

        result = await self._manager.apply_revision(
            request,
            document_ast=payload.get("document_ast"),
            context=payload.get("context") or {},
            brand_profile=payload.get("brand_profile"),
            client_id=UUID(str(payload["client_id"])) if payload.get("client_id") else None,
            project_id=UUID(str(payload["project_id"])) if payload.get("project_id") else None,
            output_format=str(payload.get("output_format") or "docx"),
            trace_id=str(payload.get("trace_id") or "-"),
        )
        memory_items = prepare_revision_memory_items(
            request,
            result,
            client_id=UUID(str(payload["client_id"])) if payload.get("client_id") else None,
            project_id=UUID(str(payload["project_id"])) if payload.get("project_id") else None,
            session_id=payload.get("session_id"),
        )

        return {
            "status": "completed",
            "skill": self.name(),
            "revision_result": result.model_dump(mode="json"),
            "memory_candidates": [item.model_dump(mode="json") for item in memory_items],
        }
