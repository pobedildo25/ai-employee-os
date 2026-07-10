from typing import Any

from app.brand_style.extractors.docx_style import DocxStyleExtractor
from app.brand_style.extractors.pdf_style import PdfStyleExtractor
from app.brand_style.extractors.pptx_style import PptxStyleExtractor
from app.brand_style.interfaces.extractor import StyleExtractor
from app.brand_style.models import BrandProfile
from app.brand_style.rules.style_rules import build_brand_profile
from app.document_intelligence.models import DocumentRepresentation
from app.file_processing.models import FileCategory


class BrandStyleExtractor:
    """Routes style extraction to format-specific extractors."""

    def __init__(self, extractors: dict[str, StyleExtractor] | None = None) -> None:
        self._extractors = extractors or {
            FileCategory.DOCX.value: DocxStyleExtractor(),
            FileCategory.PPTX.value: PptxStyleExtractor(),
            FileCategory.PDF.value: PdfStyleExtractor(),
        }

    def extract(
        self,
        document_representation: DocumentRepresentation,
        *,
        file_bytes: bytes | None = None,
        filename: str | None = None,
        client_id: str | None = None,
        profile_name: str | None = None,
    ) -> BrandProfile:
        document_type = document_representation.document_type
        extractor = self._extractors.get(document_type)
        if extractor is None:
            raw_style = {
                "format": document_type,
                "fonts": [],
                "font_sizes": [],
                "text_colors": [],
            }
        else:
            raw_style = extractor.extract(
                document_representation,
                file_bytes=file_bytes,
                filename=filename,
            )

        from uuid import UUID

        client_uuid = UUID(str(client_id)) if client_id else None
        name = profile_name or f"Brand Profile — {document_representation.title}"

        return build_brand_profile(
            raw_style=raw_style,
            client_id=client_uuid,
            name=name,
            source_artifact_id=document_representation.artifact_id,
        )

    def extract_raw(
        self,
        document_representation: DocumentRepresentation,
        *,
        file_bytes: bytes | None = None,
        filename: str | None = None,
    ) -> dict[str, Any]:
        extractor = self._extractors.get(document_representation.document_type)
        if extractor is None:
            return {"format": document_representation.document_type}
        return extractor.extract(
            document_representation,
            file_bytes=file_bytes,
            filename=filename,
        )
