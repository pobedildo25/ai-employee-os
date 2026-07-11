from app.orchestration.models import ExecutionGraph, NodeStatus


class ExecutionValidationError(Exception):
    """Raised when execution graph validation fails."""


class ExecutionValidator:
    def validate_graph(self, graph: ExecutionGraph) -> None:
        if not graph.nodes:
            return

        node_ids = set(graph.nodes.keys())
        for node_id, node in graph.nodes.items():
            for dep in node.dependencies:
                dep_id = str(dep)
                if dep_id not in node_ids:
                    raise ExecutionValidationError(
                        f"Node {node_id} depends on unknown node {dep_id}"
                    )
                if dep_id == node_id:
                    raise ExecutionValidationError(f"Node {node_id} cannot depend on itself")

        if _has_cycle(graph):
            raise ExecutionValidationError("Execution graph contains a dependency cycle")

    def validate_node_status_transition(
        self,
        current: NodeStatus,
        new: NodeStatus,
    ) -> bool:
        allowed: dict[NodeStatus, set[NodeStatus]] = {
            NodeStatus.WAITING: {NodeStatus.READY, NodeStatus.WAITING, NodeStatus.PAUSED, NodeStatus.CANCELLED, NodeStatus.FAILED},
            NodeStatus.READY: {NodeStatus.RUNNING, NodeStatus.PAUSED, NodeStatus.CANCELLED, NodeStatus.FAILED},
            NodeStatus.RUNNING: {NodeStatus.COMPLETED, NodeStatus.FAILED, NodeStatus.CANCELLED},
            NodeStatus.PAUSED: {NodeStatus.WAITING, NodeStatus.CANCELLED},
            NodeStatus.COMPLETED: set(),
            NodeStatus.FAILED: set(),
            NodeStatus.CANCELLED: set(),
        }
        return new in allowed.get(current, set())


def _has_cycle(graph: ExecutionGraph) -> bool:
    visited: set[str] = set()
    stack: set[str] = set()

    def visit(node_id: str) -> bool:
        if node_id in stack:
            return True
        if node_id in visited:
            return False
        visited.add(node_id)
        stack.add(node_id)
        node = graph.nodes[node_id]
        for dep in node.dependencies:
            if visit(str(dep)):
                return True
        stack.remove(node_id)
        return False

    return any(visit(node_id) for node_id in graph.nodes)
