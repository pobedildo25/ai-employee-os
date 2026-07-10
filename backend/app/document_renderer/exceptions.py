class RendererError(Exception):
    """Base document renderer error."""


class RenderValidationError(RendererError):
    """Raised when a render request fails validation."""


class UnsupportedFormatError(RendererError):
    """Raised when the requested output format is not supported."""


class RenderExecutionError(RendererError):
    """Raised when document rendering fails."""
