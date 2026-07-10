from abc import ABC, abstractmethod

from app.file_processing.models import ExtractedContent


class Extractor(ABC):
    @abstractmethod
    def extract(self, file_path: str) -> ExtractedContent:
        """Extract content from a file at the given path."""
        ...
