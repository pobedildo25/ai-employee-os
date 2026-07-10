import mimetypes
from pathlib import Path

from app.file_processing.models import DetectedFile, FileCategory

MIME_TO_CATEGORY: dict[str, FileCategory] = {
    "application/pdf": FileCategory.PDF,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": FileCategory.DOCX,
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": FileCategory.PPTX,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": FileCategory.XLSX,
    "text/plain": FileCategory.TEXT,
    "image/png": FileCategory.IMAGE,
    "image/jpeg": FileCategory.IMAGE,
    "image/jpg": FileCategory.IMAGE,
}

EXTENSION_TO_CATEGORY: dict[str, FileCategory] = {
    ".pdf": FileCategory.PDF,
    ".docx": FileCategory.DOCX,
    ".pptx": FileCategory.PPTX,
    ".xlsx": FileCategory.XLSX,
    ".txt": FileCategory.TEXT,
    ".png": FileCategory.IMAGE,
    ".jpg": FileCategory.IMAGE,
    ".jpeg": FileCategory.IMAGE,
}


class FileDetector:
    def detect(self, filename: str, mime_type: str | None = None, data: bytes | None = None) -> DetectedFile:
        path = Path(filename)
        extension = path.suffix.lower()

        detected_mime = mime_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        if detected_mime == "application/octet-stream" and data:
            detected_mime = self._detect_mime_from_magic(data) or detected_mime

        category = MIME_TO_CATEGORY.get(detected_mime)
        if category is None:
            category = EXTENSION_TO_CATEGORY.get(extension, FileCategory.UNKNOWN)

        return DetectedFile(
            mime_type=detected_mime,
            extension=extension,
            category=category,
            filename=path.name,
        )

    def _detect_mime_from_magic(self, data: bytes) -> str | None:
        if data.startswith(b"%PDF"):
            return "application/pdf"
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if data.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if data.startswith(b"PK\x03\x04"):
            return None
        try:
            data[:1024].decode("utf-8")
            return "text/plain"
        except UnicodeDecodeError:
            return None
