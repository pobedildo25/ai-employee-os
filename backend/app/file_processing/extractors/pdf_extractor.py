from pypdf import PdfReader

from app.file_processing.interfaces.extractor import Extractor
from app.file_processing.models import ExtractedContent


class PdfExtractor(Extractor):
    def extract(self, file_path: str) -> ExtractedContent:
        reader = PdfReader(file_path)
        page_texts: list[str] = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            page_texts.append(page_text)

        full_text = "\n\n".join(page_texts).strip()
        page_count = len(reader.pages)

        return ExtractedContent(
            text=full_text or None,
            metadata={"page_count": page_count, "format": "pdf"},
            pages=page_count,
            structure={"pages": [{"index": i + 1, "text_length": len(t)} for i, t in enumerate(page_texts)]},
        )
