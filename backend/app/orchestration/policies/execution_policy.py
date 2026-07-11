from app.orchestration.models import ExecutionControlStatus, ExecutionGraph, ExecutionState, NodeStatus


def should_continue_execution(state: ExecutionState, graph: ExecutionGraph) -> bool:
    if state.control_status in {
        ExecutionControlStatus.CANCELLED,
        ExecutionControlStatus.PAUSED,
        ExecutionControlStatus.COMPLETED,
        ExecutionControlStatus.FAILED,
    }:
        return False
    pending = any(
        node.status not in {NodeStatus.COMPLETED, NodeStatus.FAILED, NodeStatus.CANCELLED}
        for node in graph.nodes.values()
    )
    return pending


def should_fail_execution(state: ExecutionState, graph: ExecutionGraph) -> bool:
    if not graph.nodes:
        return False
    terminal = {NodeStatus.COMPLETED, NodeStatus.FAILED, NodeStatus.CANCELLED}
    if not all(node.status in terminal for node in graph.nodes.values()):
        return False
    return any(node.status == NodeStatus.FAILED for node in graph.nodes.values())


def can_resume(state: ExecutionState) -> bool:
    return state.control_status == ExecutionControlStatus.PAUSED


def can_pause(state: ExecutionState) -> bool:
    return state.control_status == ExecutionControlStatus.RUNNING


def can_cancel(state: ExecutionState) -> bool:
    return state.control_status in {
        ExecutionControlStatus.RUNNING,
        ExecutionControlStatus.PAUSED,
    }
