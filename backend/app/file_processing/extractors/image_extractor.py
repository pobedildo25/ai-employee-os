import struct
from pathlib import Path

from app.file_processing.interfaces.extractor import Extractor
from app.file_processing.models import ExtractedContent


class ImageExtractor(Extractor):
    def extract(self, file_path: str) -> ExtractedContent:
        path = Path(file_path)
        data = path.read_bytes()
        extension = path.suffix.lower().lstrip(".")

        metadata: dict[str, object] = {
            "format": extension,
            "size_bytes": len(data),
        }

        if extension == "png":
            metadata.update(self._parse_png_metadata(data))
        elif extension in {"jpg", "jpeg"}:
            metadata.update(self._parse_jpeg_metadata(data))

        return ExtractedContent(
            text=None,
            metadata=metadata,
            structure={"image": metadata},
        )

    def _parse_png_metadata(self, data: bytes) -> dict[str, object]:
        if len(data) < 24 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
            return {}
        width, height = struct.unpack(">II", data[16:24])
        return {"width": width, "height": height, "mime_type": "image/png"}

    def _parse_jpeg_metadata(self, data: bytes) -> dict[str, object]:
        if not data.startswith(b"\xff\xd8"):
            return {}
        index = 2
        while index < len(data):
            if data[index] != 0xFF:
                break
            marker = data[index + 1]
            index += 2
            if marker in {0xC0, 0xC2}:
                height = int.from_bytes(data[index + 3 : index + 5], "big")
                width = int.from_bytes(data[index + 5 : index + 7], "big")
                return {"width": width, "height": height, "mime_type": "image/jpeg"}
            segment_length = int.from_bytes(data[index : index + 2], "big")
            index += segment_length
        return {"mime_type": "image/jpeg"}
