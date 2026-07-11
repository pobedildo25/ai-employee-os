import logging
from typing import Any
from uuid import UUID

from app.brand_style.extractor import BrandStyleExtractor
from app.brand_style.models import BrandProfile
from app.document_intelligence.ast.models import DocumentAST
from app.document_intelligence.models import DocumentRepresentation
from app.document_intelligence.pipeline import DocumentPipeline
from app.knowledge.extractor import KnowledgeExtractor
from app.knowledge.manager import KnowledgeManager
from app.knowledge.memory_preparer import prepare_knowledge_memory_items
from app.knowledge.models import KnowledgeItem, KnowledgeMigrationResult

logger = logging.getLogger(__name__)


class KnowledgeMigrationService:
    """Migrates client document archives into Client Knowledge Base."""

    def __init__(
        self,
        extractor: KnowledgeExtractor,
        manager: KnowledgeManager,
        document_pipeline: DocumentPipeline | None = None,
        brand_extractor: BrandStyleExtractor | None = None,
    ) -> None:
        self._extractor = extractor
        self._manager = manager
        self._document_pipeline = document_pipeline or DocumentPipeline()
        self._brand_extractor = brand_extractor or BrandStyleExtractor()

    async def migrate(
        self,
        *,
        client_id: UUID,
        artifacts: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
        file_bytes_by_artifact: dict[str, bytes] | None = None,
        persist: bool = True,
        trace_id: str = "-",
    ) -> KnowledgeMigrationResult:
        processed: list[UUID] = []
        extracted: list[KnowledgeItem] = []
        brand_profiles: list[dict[str, Any]] = []
        warnings: list[str] = []
        file_bytes_by_artifact = file_bytes_by_artifact or {}

        for artifact in artifacts:
            artifact_id = _parse_uuid(artifact.get("id") or artifact.get("artifact_id"))
            if artifact_id is None:
                warnings.append("Skipped artifact without id")
                continue

            try:
                representation, document_ast = await self._resolve_document(
                    artifact=artifact,
                    artifact_id=artifact_id,
                    file_bytes=file_bytes_by_artifact.get(str(artifact_id)),
                )
            except Exception as exc:
                warnings.append(f"Failed to process artifact {artifact_id}: {exc}")
                logger.warning(
                    "knowledge migration artifact failed | trace_id=%s artifact_id=%s error=%s",
                    trace_id,
                    artifact_id,
                    exc,
                )
                continue

            brand_profile = self._extract_brand_profile(
                representation=representation,
                file_bytes=file_bytes_by_artifact.get(str(artifact_id)),
                filename=artifact.get("name") or artifact.get("filename"),
                client_id=client_id,
            )
            if brand_profile is not None:
                brand_profiles.append(brand_profile.model_dump(mode="json"))

            items = await self._extractor.extract(
                representation=representation,
                document_ast=document_ast,
                brand_profile=brand_profile,
                context={**(context or {}), "artifact": artifact},
                trace_id=trace_id,
            )
            for item in items:
                item.client_id = client_id
                item.source_artifact_id = artifact_id

            if persist and items:
                await self._manager.add_many(items)

            extracted.extend(items)
            processed.append(artifact_id)

        result = KnowledgeMigrationResult(
            processed_artifacts=processed,
            extracted_items=extracted,
            brand_profiles=brand_profiles,
            warnings=warnings,
        )
        memory_items = prepare_knowledge_memory_items(result, client_id=client_id)
        result.memory_candidates = [item.model_dump(mode="json") for item in memory_items]
        return result

    async def _resolve_document(
        self,
        *,
        artifact: dict[str, Any],
        artifact_id: UUID,
        file_bytes: bytes | None,
    ) -> tuple[DocumentRepresentation, DocumentAST | None]:
        metadata = artifact.get("metadata") or {}
        representation_raw = metadata.get("document_representation")
        ast_raw = metadata.get("document_ast")

        if representation_raw:
            representation = DocumentRepresentation.model_validate(representation_raw)
            document_ast = DocumentAST.model_validate(ast_raw) if ast_raw else None
            return representation, document_ast

        if file_bytes is not None:
            representation, document_ast, _extracted, _detected = self._document_pipeline.process_bytes(
                artifact_id=artifact_id,
                title=str(artifact.get("name") or "Document"),
                data=file_bytes,
                filename=str(artifact.get("name") or "document.bin"),
                mime_type=artifact.get("mime_type"),
            )
            return representation, document_ast

        raise ValueError("Artifact has no document representation and no file bytes")

    def _extract_brand_profile(
        self,
        *,
        representation: DocumentRepresentation,
        file_bytes: bytes | None,
        filename: str | None,
        client_id: UUID,
    ) -> BrandProfile | None:
        if representation.document_type not in {"docx", "pptx", "pdf"}:
            return None
        try:
            return self._brand_extractor.extract(
                representation,
                file_bytes=file_bytes,
                filename=filename,
                client_id=str(client_id),
            )
        except Exception:
            return None


def _parse_uuid(value: object | None) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except ValueError:
        return None
