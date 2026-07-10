import tempfile
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from app.brand_style.interfaces.extractor import StyleExtractor
from app.document_intelligence.models import DocumentRepresentation


class PdfStyleExtractor(StyleExtractor):
    def extract(
        self,
        document_representation: DocumentRepresentation,
        *,
        file_bytes: bytes | None = None,
        filename: str | None = None,
    ) -> dict[str, Any]:
        if not file_bytes:
            return self._extract_from_representation(document_representation)

        suffix = Path(filename or "document.pdf").suffix or ".pdf"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            reader = PdfReader(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        page_sizes: list[dict[str, float]] = []
        fonts: set[str] = set()
        image_count = 0
        block_structure: list[dict[str, Any]] = []

        for index, page in enumerate(reader.pages, start=1):
            mediabox = page.mediabox
            page_sizes.append(
                {
                    "page": index,
                    "width": float(mediabox.width),
                    "height": float(mediabox.height),
                }
            )
            block_structure.append(
                {
                    "page": index,
                    "text_length": len(page.extract_text() or ""),
                }
            )

            resources = page.get("/Resources")
            if resources and "/Font" in resources:
                font_dict = resources["/Font"].get_object()
                for font_name in font_dict:
                    fonts.add(str(font_name))

            if resources and "/XObject" in resources:
                xobjects = resources["/XObject"].get_object()
                for obj_name in xobjects:
                    obj = xobjects[obj_name].get_object()
                    if obj.get("/Subtype") == "/Image":
                        image_count += 1

        return {
            "format": "pdf",
            "page_count": len(reader.pages),
            "page_sizes": page_sizes,
            "fonts": sorted(fonts),
            "image_count": image_count,
            "block_structure": block_structure,
        }

    def _extract_from_representation(self, representation: DocumentRepresentation) -> dict[str, Any]:
        structure = representation.structure
        return {
            "format": "pdf",
            "page_count": structure.get("pages", 0),
            "section_count": structure.get("section_count", 0),
            "block_structure": structure.get("node_types", {}),
        }
