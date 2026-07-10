from docx import Document

from app.file_processing.interfaces.extractor import Extractor
from app.file_processing.models import ExtractedContent


class DocxExtractor(Extractor):
    def extract(self, file_path: str) -> ExtractedContent:
        document = Document(file_path)
        paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
        full_text = "\n".join(paragraphs).strip()

        return ExtractedContent(
            text=full_text or None,
            metadata={"paragraph_count": len(paragraphs), "format": "docx"},
            structure={"paragraphs": paragraphs},
        )
