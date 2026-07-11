import logging
from typing import Any

from app.core.logging import trace_id_var


class ObservabilityLogger:
    """Centralized observation logger — uses existing trace_id, does not replace logging."""

    def __init__(self, name: str = "app.observability") -> None:
        self._logger = logging.getLogger(name)

    def bind_trace(self, trace_id: str) -> None:
        trace_id_var.set(trace_id)

    def info(self, message: str, **fields: Any) -> None:
        self._logger.info(self._format(message, fields))

    def warning(self, message: str, **fields: Any) -> None:
        self._logger.warning(self._format(message, fields))

    def error(self, message: str, **fields: Any) -> None:
        self._logger.error(self._format(message, fields))

    def debug(self, message: str, **fields: Any) -> None:
        self._logger.debug(self._format(message, fields))

    @staticmethod
    def _format(message: str, fields: dict[str, Any]) -> str:
        if not fields:
            return message
        extras = " ".join(f"{key}={value}" for key, value in fields.items())
        return f"{message} | {extras}"
