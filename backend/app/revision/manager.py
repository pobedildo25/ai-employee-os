from typing import Any
from uuid import UUID

from app.brand_style.models import BrandProfile
from app.document_intelligence.ast.models import DocumentAST
from app.document_renderer.models import OutputFormat, RenderRequest
from app.document_renderer.renderer import DocumentRendererService, RenderArtifactService
from app.revision.agent import RevisionAgent
from app.revision.models import RevisionRequest, RevisionResult, RevisionStatus
from app.revision.policies.revision_policy import can_auto_revise, next_revision_count, should_wait_for_user
from app.schemas.artifact import ArtifactNewVersionRequest
from app.services.artifact_service import ArtifactService


class RevisionManager:
    """Coordinates revision planning, AST update, and artifact versioning."""

    def __init__(
        self,
        agent: RevisionAgent,
        renderer_service: DocumentRendererService | None = None,
        artifact_service: ArtifactService | None = None,
        render_artifact_service: RenderArtifactService | None = None,
    ) -> None:
        self._agent = agent
        self._renderer_service = renderer_service or DocumentRendererService()
        self._artifact_service = artifact_service
        self._render_artifact_service = render_artifact_service or RenderArtifactService(
            renderer_service=self._renderer_service,
            artifact_service=artifact_service,
        )

    async def apply_revision(
        self,
        request: RevisionRequest,
        *,
        document_ast: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        brand_profile: BrandProfile | dict[str, Any] | None = None,
        client_id: UUID | None = None,
        project_id: UUID | None = None,
        output_format: str = "docx",
        trace_id: str = "-",
    ) -> RevisionResult:
        if should_wait_for_user(request.revision_count):
            return RevisionResult(
                artifact_id=request.source_artifact_id,
                summary="Automatic revision limit reached — waiting for user decision",
                status=RevisionStatus.WAITING_USER,
                document_ast=document_ast,
                metadata={"revision_count": request.revision_count},
            )

        if not can_auto_revise(request.revision_count):
            return RevisionResult(
                artifact_id=request.source_artifact_id,
                summary="Revision not allowed by policy",
                status=RevisionStatus.WAITING_USER,
                document_ast=document_ast,
            )

        working_request = request.model_copy(
            update={"revision_count": next_revision_count(request.revision_count)}
        )

        planned = await self._agent.revise(
            working_request,
            document_ast=document_ast,
            context=context,
            trace_id=trace_id,
        )

        if planned.status == RevisionStatus.FAILED:
            return planned

        updated_ast = planned.document_ast or document_ast
        needs_render = bool((planned.metadata or {}).get("needs_render", True))
        if not needs_render or updated_ast is None:
            return planned.model_copy(
                update={
                    "status": RevisionStatus.COMPLETED,
                    "summary": planned.summary or "AST updated without re-render",
                }
            )

        profile = None
        if brand_profile is not None:
            profile = (
                brand_profile
                if isinstance(brand_profile, BrandProfile)
                else BrandProfile.model_validate(brand_profile)
            )

        try:
            format_value = OutputFormat(str(output_format).lower())
        except ValueError:
            format_value = OutputFormat.DOCX

        ast_model = DocumentAST.model_validate(updated_ast)
        render_request = RenderRequest(
            document_structure=ast_model,
            brand_profile=profile,
            output_format=format_value,
            metadata={"title": (context or {}).get("title") or "Revised Document"},
            client_id=client_id,
            project_id=project_id,
            name=f"revised.{format_value.value}",
            source_artifact_id=UUID(str(request.source_artifact_id))
            if request.source_artifact_id
            else None,
        )

        render_result = await self._store_revision(render_request, working_request)

        return planned.model_copy(
            update={
                "artifact_id": render_result.artifact_id or request.source_artifact_id,
                "version_id": (render_result.metadata or {}).get("version_id"),
                "status": RevisionStatus.COMPLETED,
                "document_ast": updated_ast,
                "metadata": {
                    **(planned.metadata or {}),
                    "render_result": render_result.model_dump(mode="json", exclude={"file_bytes"}),
                    "revision_count": working_request.revision_count,
                },
            }
        )

    async def _store_revision(
        self,
        render_request: RenderRequest,
        revision_request: RevisionRequest,
    ):
        render_result = self._renderer_service.render(render_request)

        if (
            self._artifact_service is not None
            and revision_request.source_artifact_id is not None
            and render_result.file_bytes is not None
        ):
            artifact_id = UUID(str(revision_request.source_artifact_id))
            version = await self._artifact_service.create_new_version(
                artifact_id,
                ArtifactNewVersionRequest(
                    change_description="Automatic quality revision",
                    metadata={
                        "generated_by": "revision_manager",
                        "revision_count": revision_request.revision_count,
                        "suggested_changes": revision_request.suggested_changes,
                        "user_feedback": revision_request.user_feedback,
                        **(render_result.metadata or {}),
                    },
                ),
                file_data=render_result.file_bytes,
                mime_type=render_result.mime_type,
            )
            return render_result.model_copy(
                update={
                    "artifact_id": artifact_id,
                    "file_path": version.storage_path,
                    "metadata": {
                        **(render_result.metadata or {}),
                        "version_id": str(version.id),
                        "version_number": version.version_number,
                        "revision_count": revision_request.revision_count,
                    },
                }
            )

        if self._render_artifact_service is not None and render_request.client_id and render_request.project_id:
            return await self._render_artifact_service.render_and_store(render_request)

        return render_result
