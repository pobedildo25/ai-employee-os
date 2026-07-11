from datetime import datetime

from app.orchestration.models import (
    ExecutionControlStatus,
    ExecutionGraph,
    ExecutionState,
    NodeStatus,
)


class StateManager:
    """Maintain unified execution state for an ExecutionGraph."""

    def create_state(self, execution_id: str, graph: ExecutionGraph) -> ExecutionState:
        waiting = [
            node_id
            for node_id, node in graph.nodes.items()
            if node.status in {NodeStatus.WAITING, NodeStatus.READY}
        ]
        return ExecutionState(
            execution_id=execution_id,
            graph_id=graph.id,
            waiting_nodes=waiting,
            progress=0.0,
        )

    def refresh(self, state: ExecutionState, graph: ExecutionGraph) -> ExecutionState:
        state.current_nodes = [
            node_id
            for node_id, node in graph.nodes.items()
            if node.status == NodeStatus.RUNNING
        ]
        state.completed_nodes = [
            node_id
            for node_id, node in graph.nodes.items()
            if node.status == NodeStatus.COMPLETED
        ]
        state.failed_nodes = [
            node_id
            for node_id, node in graph.nodes.items()
            if node.status == NodeStatus.FAILED
        ]
        state.waiting_nodes = [
            node_id
            for node_id, node in graph.nodes.items()
            if node.status in {NodeStatus.WAITING, NodeStatus.READY, NodeStatus.PAUSED}
        ]
        state.updated_at = datetime.now()
        return state

    def pause(self, state: ExecutionState) -> ExecutionState:
        state.control_status = ExecutionControlStatus.PAUSED
        state.updated_at = datetime.now()
        return state

    def resume(self, state: ExecutionState) -> ExecutionState:
        if state.control_status == ExecutionControlStatus.PAUSED:
            state.control_status = ExecutionControlStatus.RUNNING
        state.updated_at = datetime.now()
        return state

    def cancel(self, state: ExecutionState, *, reason: str | None = None) -> ExecutionState:
        state.control_status = ExecutionControlStatus.CANCELLED
        state.failure_reason = reason
        state.updated_at = datetime.now()
        return state

    def complete(self, state: ExecutionState) -> ExecutionState:
        state.control_status = ExecutionControlStatus.COMPLETED
        state.current_nodes = []
        state.updated_at = datetime.now()
        return state

    def fail(self, state: ExecutionState, reason: str) -> ExecutionState:
        state.control_status = ExecutionControlStatus.FAILED
        state.failure_reason = reason
        state.current_nodes = []
        state.updated_at = datetime.now()
        return state

    def is_paused(self, state: ExecutionState) -> bool:
        return state.control_status == ExecutionControlStatus.PAUSED

    def is_cancelled(self, state: ExecutionState) -> bool:
        return state.control_status == ExecutionControlStatus.CANCELLED
