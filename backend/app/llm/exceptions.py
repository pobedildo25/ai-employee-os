class LLMError(Exception):
    """Base exception for LLM Gateway errors."""


class LLMProviderError(LLMError):
    """Raised when the underlying LLM provider fails."""


class LLMConfigurationError(LLMError):
    """Raised when LLM Gateway is misconfigured."""


class LLMAuthenticationError(LLMProviderError):
    """Raised when API authentication fails."""


class LLMRateLimitError(LLMProviderError):
    """Raised when the provider rate-limits requests."""


class LLMModelNotAvailableError(LLMProviderError):
    """Raised when the requested model is unavailable."""
