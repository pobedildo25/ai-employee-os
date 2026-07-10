class AgentRuntimeError(Exception):
    """Base exception for agent runtime errors."""


class GraphBuildError(AgentRuntimeError):
    """Raised when graph construction or compilation fails."""


class GraphExecutionError(AgentRuntimeError):
    """Raised when graph execution fails."""


class CheckpointError(AgentRuntimeError):
    """Raised when checkpoint save/load/delete fails."""
