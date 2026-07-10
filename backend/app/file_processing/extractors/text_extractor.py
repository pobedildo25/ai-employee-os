from pathlib import Path

from app.file_processing.interfaces.extractor import Extractor
from app.file_processing.models import ExtractedContent


class TextExtractor(Extractor):
    def extract(self, file_path: str) -> ExtractedContent:
        content = Path(file_path).read_text(encoding="utf-8")
        line_count = len(content.splitlines()) if content else 0

        return ExtractedContent(
            text=content or None,
            metadata={"line_count": line_count, "char_count": len(content), "format": "txt"},
            structure={"lines": content.splitlines()},
        )
