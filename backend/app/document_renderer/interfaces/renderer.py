"""Format-specific renderer port.

Product entry for rendering is ``DocumentRendererService.render(RenderRequest)``
(the unified Render Contract). Implementations here are format adapters only.
"""

from abc import ABC, abstractmethod

from app.document_renderer.models import RenderRequest, RenderResult


class DocumentRenderer(ABC):
    @abstractmethod
    def validate(self, request: RenderRequest) -> None:
        """Validate that the request can be rendered."""

    @abstractmethod
    def render(self, request: RenderRequest) -> RenderResult:
        """Render document bytes from the request."""
