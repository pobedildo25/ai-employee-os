from typing import Any
from uuid import UUID

from app.document_intelligence.analyzer import DocumentAnalyzer
from app.document_intelligence.memory_preparer import prepare_document_memory_items
from app.document_intelligence.models import AnalysisStatus
from app.document_intelligence.pipeline import DocumentPipeline
from app.file_processing.models import ExtractedContent
from app.skills.base.skill import BaseSkill
from app.skills.models import Capability, SkillMetadata


class DocumentAnalysisSkill(BaseSkill):
    """Provides document analysis capability — understanding and structure only."""

    def __init__(
        self,
        pipeline: DocumentPipeline | None = None,
        analyzer: DocumentAnalyzer | None = None,
    ) -> None:
        self._pipeline = pipeline or DocumentPipeline(analyzer=analyzer or DocumentAnalyzer())
        super().__init__(
            metadata=SkillMetadata(
                id="document_analysis_skill",
                name="document_analysis_skill",
                description="Анализ и понимание структуры документов",
                capabilities=["document_analysis"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "artifact_id": {"type": "string"},
                        "title": {"type": "string"},
                        "extracted_content": {"type": "object"},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "representation": {"type": "object"},
                    },
                },
            ),
            capabilities=[
                Capability(
                    name="document_analysis",
                    description="Анализ содержимого и структуры документов",
                    category="document",
                ),
            ],
        )

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        artifact_id_raw = payload.get("artifact_id")
        extracted_raw = payload.get("extracted_content")
        title = str(payload.get("title") or payload.get("description") or "Untitled")

        if extracted_raw is None:
            return {
                "status": "failed",
                "skill": self.name(),
                "message": "extracted_content is required for document analysis",
                "payload_keys": list(payload.keys()),
            }

        artifact_id = UUID(str(artifact_id_raw)) if artifact_id_raw else UUID(int=0)
        extracted = (
            extracted_raw
            if isinstance(extracted_raw, ExtractedContent)
            else ExtractedContent.model_validate(extracted_raw)
        )

        representation, document_ast = self._pipeline.analyze_extracted(
            artifact_id=artifact_id,
            title=title,
            extracted=extracted,
        )
        memory_items = prepare_document_memory_items(representation)

        return {
            "status": "completed",
            "skill": self.name(),
            "analysis_status": AnalysisStatus.COMPLETED.value,
            "representation": representation.model_dump(mode="json"),
            "document_ast": document_ast.model_dump(mode="json"),
            "memory_candidates": [item.model_dump(mode="json") for item in memory_items],
        }
