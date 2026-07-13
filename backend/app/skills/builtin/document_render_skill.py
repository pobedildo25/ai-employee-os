from typing import Any
from uuid import UUID

from app.brand_style.models import BrandProfile
from app.document_intelligence.ast.models import DocumentAST
from app.document_renderer.models import OutputFormat, RenderRequest
from app.document_renderer.renderer import DocumentRendererService, RenderArtifactService
from app.skills.base.skill import BaseSkill
from app.skills.models import Capability, SkillMetadata


class DocumentRenderSkill(BaseSkill):
    """Renders documents from AST and brand profile into generated artifacts."""

    def __init__(
        self,
        renderer_service: DocumentRendererService | None = None,
        artifact_service: RenderArtifactService | None = None,
    ) -> None:
        self._renderer_service = renderer_service or DocumentRendererService()
        self._artifact_service = artifact_service or RenderArtifactService(self._renderer_service)
        super().__init__(
            metadata=SkillMetadata(
                id="document_render_skill",
                name="document_render_skill",
                description="Универсальный рендеринг документов из AST и Brand Profile",
                capabilities=["document_rendering"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "document_ast": {"type": "object"},
                        "brand_profile": {"type": "object"},
                        "output_format": {"type": "string"},
                        "client_id": {"type": "string"},
                        "project_id": {"type": "string"},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "render_result": {"type": "object"},
                    },
                },
            ),
            capabilities=[
                Capability(
                    name="document_rendering",
                    description="Генерация документов из структуры и фирменного стиля",
                    category="document",
                ),
            ],
        )

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        ast_raw = payload.get("document_ast") or payload.get("document_structure")
        if ast_raw is None:
            return {
                "status": "failed",
                "skill": self.name(),
                "message": "document_ast is required for document rendering",
                "payload_keys": list(payload.keys()),
            }

        document_ast = ast_raw if isinstance(ast_raw, DocumentAST) else DocumentAST.model_validate(ast_raw)

        brand_profile = None
        brand_raw = payload.get("brand_profile")
        if brand_raw is not None:
            brand_profile = (
                brand_raw if isinstance(brand_raw, BrandProfile) else BrandProfile.model_validate(brand_raw)
            )

        output_format_raw = (
            payload.get("output_format")
            or (payload.get("metadata") or {}).get("document_type")
            or (payload.get("context") or {}).get("document_type")
            or "docx"
        )
        try:
            output_format = OutputFormat(str(output_format_raw).lower())
        except ValueError:
            return {
                "status": "failed",
                "skill": self.name(),
                "message": f"Unsupported output format: {output_format_raw}",
            }

        request = RenderRequest(
            document_structure=document_ast,
            brand_profile=brand_profile,
            output_format=output_format,
            metadata=dict(payload.get("metadata") or {}),
            client_id=UUID(str(payload["client_id"])) if payload.get("client_id") else None,
            project_id=UUID(str(payload["project_id"])) if payload.get("project_id") else None,
            name=payload.get("name"),
            source_artifact_id=UUID(str(payload["source_artifact_id"]))
            if payload.get("source_artifact_id")
            else None,
            brand_profile_id=UUID(str(payload["brand_profile_id"]))
            if payload.get("brand_profile_id")
            else (brand_profile.id if brand_profile else None),
        )

        # Skill owns store default: persist when workspace ids are present unless explicitly disabled.
        store_artifact = payload.get("store_artifact")
        if store_artifact is None:
            store_artifact = bool(request.client_id and request.project_id)
        if store_artifact and request.client_id and request.project_id:
            try:
                render_result = await self._artifact_service.render_and_store(request)
            except Exception as exc:
                return {
                    "status": "failed",
                    "skill": self.name(),
                    "message": f"document render failed: {exc}",
                }
        else:
            try:
                render_result = self._renderer_service.render(request)
            except Exception as exc:
                return {
                    "status": "failed",
                    "skill": self.name(),
                    "message": f"document render failed: {exc}",
                }

        render_payload = render_result.model_dump(mode="json", exclude={"file_bytes"})
        if render_result.file_bytes is not None:
            render_payload["file_size"] = len(render_result.file_bytes)

        return {
            "status": "completed",
            "skill": self.name(),
            "render_result": render_payload,
        }
