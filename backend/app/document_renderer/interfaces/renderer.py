from abc import ABC, abstractmethod

from app.document_renderer.models import RenderRequest, RenderResult


class DocumentRenderer(ABC):
    @abstractmethod
    def validate(self, request: RenderRequest) -> None:
        """Validate that the request can be rendered."""

    @abstractmethod
    def render(self, request: RenderRequest) -> RenderResult:
        """Render document bytes from the request."""
