from typing import Any
from uuid import UUID

from app.brand_style.extractor import BrandStyleExtractor
from app.brand_style.profile_manager import BrandProfileManager, prepare_brand_memory_items
from app.document_intelligence.models import DocumentRepresentation
from app.skills.base.skill import BaseSkill
from app.skills.models import Capability, SkillMetadata


class BrandStyleAnalysisSkill(BaseSkill):
    """Extracts brand style from documents and returns BrandProfile data."""

    def __init__(
        self,
        extractor: BrandStyleExtractor | None = None,
        profile_manager: BrandProfileManager | None = None,
    ) -> None:
        self._extractor = extractor or BrandStyleExtractor()
        self._profile_manager = profile_manager or BrandProfileManager()
        super().__init__(
            metadata=SkillMetadata(
                id="brand_style_analysis_skill",
                name="brand_style_analysis_skill",
                description="Извлечение фирменного стиля из документов",
                capabilities=["brand_style_analysis"],
                input_schema={
                    "type": "object",
                    "properties": {
                        "document_representation": {"type": "object"},
                        "file_bytes": {"type": "string"},
                        "filename": {"type": "string"},
                        "client_id": {"type": "string"},
                        "client_name": {"type": "string"},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "brand_profile": {"type": "object"},
                    },
                },
            ),
            capabilities=[
                Capability(
                    name="brand_style_analysis",
                    description="Анализ и извлечение фирменного стиля документов",
                    category="brand",
                ),
            ],
        )

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        representation_raw = payload.get("document_representation")
        if representation_raw is None:
            return {
                "status": "failed",
                "skill": self.name(),
                "message": "document_representation is required for brand style analysis",
                "payload_keys": list(payload.keys()),
            }

        representation = (
            representation_raw
            if isinstance(representation_raw, DocumentRepresentation)
            else DocumentRepresentation.model_validate(representation_raw)
        )

        file_bytes = payload.get("file_bytes")
        if isinstance(file_bytes, str):
            file_bytes = file_bytes.encode("utf-8")

        profile = self._extractor.extract(
            representation,
            file_bytes=file_bytes,
            filename=payload.get("filename"),
            client_id=payload.get("client_id"),
            profile_name=payload.get("profile_name"),
        )
        saved_profile = self._profile_manager.create_profile(profile)
        memory_items = prepare_brand_memory_items(
            saved_profile,
            client_name=payload.get("client_name"),
            session_id=payload.get("session_id"),
        )

        return {
            "status": "completed",
            "skill": self.name(),
            "brand_profile": saved_profile.model_dump(mode="json"),
            "raw_style": self._extractor.extract_raw(
                representation,
                file_bytes=file_bytes,
                filename=payload.get("filename"),
            ),
            "memory_candidates": [item.model_dump(mode="json") for item in memory_items],
            "artifact_metadata_patch": {
                "brand_style_extraction": {
                    "status": "completed",
                    "profile_id": str(saved_profile.id),
                    "document_type": representation.document_type,
                    "colors": saved_profile.colors,
                    "typography": saved_profile.typography,
                }
            },
        }
