from uuid import UUID
import logging

from app.document_renderer.builders.document_builder import DocumentBuilder
from app.document_renderer.exceptions import UnsupportedFormatError
from app.document_renderer.interfaces.renderer import DocumentRenderer
from app.document_renderer.models import OutputFormat, RenderRequest, RenderResult
from app.document_renderer.renderers.docx_renderer import DocxRenderer
from app.document_renderer.renderers.pdf_renderer import PdfRenderer
from app.document_renderer.renderers.pptx_renderer import PptxRenderer
from app.repositories.artifact_repository import ArtifactRepository
from app.repositories.artifact_version_repository import ArtifactVersionRepository
from app.schemas.artifact import ArtifactUploadRequest
from app.services.artifact_service import ArtifactService
from app.storage.storage_interface import StorageInterface

logger = logging.getLogger(__name__)


class DocumentRendererService:
    """Unified Render Contract entry: ``render(RenderRequest)``.

    Skills and product code must call this service (not format renderers directly).
    PDF remains a stub and must not be advertised as available.
    """

    def __init__(
        self,
        renderers: dict[OutputFormat, DocumentRenderer] | None = None,
        document_builder: DocumentBuilder | None = None,
    ) -> None:
        self._renderers = renderers or {
            OutputFormat.DOCX: DocxRenderer(),
            OutputFormat.PPTX: PptxRenderer(),
            OutputFormat.PDF: PdfRenderer(),
        }
        self._document_builder = document_builder or DocumentBuilder()

    def render(self, request: RenderRequest) -> RenderResult:
        self._document_builder.validate_ast(request.document_structure)
        renderer = self._renderers.get(request.output_format)
        if renderer is None:
            raise UnsupportedFormatError(f"Unsupported output format: {request.output_format}")
        renderer.validate(request)
        return renderer.render(request)


class RenderArtifactService:
    """Renders documents and persists them as generated artifacts."""

    GENERATED_ARTIFACT_TYPE = "generated_document"

    def __init__(
        self,
        renderer_service: DocumentRendererService | None = None,
        artifact_service: ArtifactService | None = None,
    ) -> None:
        self._renderer_service = renderer_service or DocumentRendererService()
        self._artifact_service = artifact_service

    async def render_and_store(self, request: RenderRequest) -> RenderResult:
        render_result = self._renderer_service.render(request)

        if self._artifact_service is None:
            return render_result

        if request.client_id is None or request.project_id is None:
            return render_result

        if render_result.file_bytes is None:
            return render_result

        artifact_name = request.name or f"generated.{request.output_format.value}"
        metadata = {
            "generated_by": "document_renderer",
            "output_format": request.output_format.value,
            "source_artifact_id": str(request.source_artifact_id) if request.source_artifact_id else None,
            "brand_profile_id": str(request.brand_profile_id or (request.brand_profile.id if request.brand_profile else None)),
            **render_result.metadata,
            **request.metadata,
        }

        try:
            artifact = await self._artifact_service.upload_artifact(
                ArtifactUploadRequest(
                    client_id=request.client_id,
                    project_id=request.project_id,
                    name=artifact_name,
                    artifact_type=self.GENERATED_ARTIFACT_TYPE,
                    description="Generated document",
                    metadata=metadata,
                ),
                file_data=render_result.file_bytes,
                mime_type=render_result.mime_type,
            )
        except Exception as exc:
            logger.warning(
                "artifact storage degraded | name=%s error=%s",
                artifact_name,
                exc,
            )
            return render_result.model_copy(
                update={
                    "metadata": {
                        **metadata,
                        "storage_degraded": True,
                        "storage_error": str(exc),
                    }
                }
            )

        return render_result.model_copy(
            update={
                "artifact_id": artifact.id,
                "file_path": artifact.storage_path,
                "metadata": metadata,
            }
        )


def create_render_artifact_service(
    artifact_repository: ArtifactRepository,
    version_repository: ArtifactVersionRepository,
    storage: StorageInterface,
) -> RenderArtifactService:
    artifact_service = ArtifactService(artifact_repository, version_repository, storage)
    return RenderArtifactService(artifact_service=artifact_service)
