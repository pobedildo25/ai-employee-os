import tempfile
from pathlib import Path

from app.file_processing.extractors.docx_extractor import DocxExtractor
from app.file_processing.extractors.image_extractor import ImageExtractor
from app.file_processing.extractors.pdf_extractor import PdfExtractor
from app.file_processing.extractors.pptx_extractor import PptxExtractor
from app.file_processing.extractors.text_extractor import TextExtractor
from app.file_processing.extractors.xlsx_extractor import XlsxExtractor
from app.file_processing.file_detector import FileDetector
from app.file_processing.interfaces.extractor import Extractor
from app.file_processing.models import DetectedFile, ExtractedContent, FileCategory


class FileProcessor:
    def __init__(self, detector: FileDetector | None = None) -> None:
        self._detector = detector or FileDetector()
        self._extractors: dict[FileCategory, Extractor] = {
            FileCategory.PDF: PdfExtractor(),
            FileCategory.DOCX: DocxExtractor(),
            FileCategory.PPTX: PptxExtractor(),
            FileCategory.XLSX: XlsxExtractor(),
            FileCategory.TEXT: TextExtractor(),
            FileCategory.IMAGE: ImageExtractor(),
        }

    def detect(self, filename: str, mime_type: str | None = None, data: bytes | None = None) -> DetectedFile:
        return self._detector.detect(filename, mime_type=mime_type, data=data)

    def process_bytes(self, data: bytes, filename: str, mime_type: str | None = None) -> ExtractedContent:
        detected = self.detect(filename, mime_type=mime_type, data=data)
        extractor = self._extractors.get(detected.category)
        if extractor is None:
            raise ValueError(f"Unsupported file category: {detected.category}")

        suffix = detected.extension or Path(filename).suffix or ""
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(data)
            tmp_path = tmp.name

        try:
            extracted = extractor.extract(tmp_path)
            extracted.metadata = {
                **extracted.metadata,
                "mime_type": detected.mime_type,
                "extension": detected.extension,
                "category": detected.category.value,
                "filename": detected.filename,
            }
            return extracted
        finally:
            Path(tmp_path).unlink(missing_ok=True)
