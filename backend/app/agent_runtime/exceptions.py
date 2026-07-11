class AgentRuntimeError(Exception):
    """Base exception for agent runtime errors."""


class GraphBuildError(AgentRuntimeError):
    """Raised when graph construction or compilation fails."""


class GraphExecutionError(AgentRuntimeError):
    """Raised when graph execution fails."""

    def __init__(
        self,
        message: str,
        *,
        execution_id: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.execution_id = execution_id
        self.trace_id = trace_id


class CheckpointError(AgentRuntimeError):
    """Raised when checkpoint save/load/delete fails."""
