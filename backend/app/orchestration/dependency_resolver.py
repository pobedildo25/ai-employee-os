from app.orchestration.models import ExecutionGraph, ExecutionGraphNode, NodeStatus


class DependencyResolver:
    """Resolve node readiness from graph dependencies only."""

    def resolve(self, graph: ExecutionGraph) -> tuple[list[ExecutionGraphNode], list[ExecutionGraphNode]]:
        ready: list[ExecutionGraphNode] = []
        waiting: list[ExecutionGraphNode] = []

        completed_ids = {
            node_id
            for node_id, node in graph.nodes.items()
            if node.status == NodeStatus.COMPLETED
        }
        failed_or_cancelled = {
            node_id
            for node_id, node in graph.nodes.items()
            if node.status in {NodeStatus.FAILED, NodeStatus.CANCELLED}
        }

        for node_id, node in graph.nodes.items():
            if node.status in {
                NodeStatus.COMPLETED,
                NodeStatus.RUNNING,
                NodeStatus.FAILED,
                NodeStatus.CANCELLED,
                NodeStatus.PAUSED,
            }:
                continue

            dep_ids = {str(dep) for dep in node.dependencies}
            if dep_ids & failed_or_cancelled:
                node.status = NodeStatus.FAILED
                node.error = node.error or "Dependency failed"
                continue

            if dep_ids <= completed_ids:
                node.status = NodeStatus.READY
                ready.append(node)
            else:
                node.status = NodeStatus.WAITING
                waiting.append(node)

        return ready, waiting

    def get_ready_nodes(self, graph: ExecutionGraph) -> list[ExecutionGraphNode]:
        ready, _ = self.resolve(graph)
        return ready

    def get_waiting_nodes(self, graph: ExecutionGraph) -> list[ExecutionGraphNode]:
        _, waiting = self.resolve(graph)
        return waiting

    def is_complete(self, graph: ExecutionGraph) -> bool:
        return all(
            node.status in {NodeStatus.COMPLETED, NodeStatus.FAILED, NodeStatus.CANCELLED}
            for node in graph.nodes.values()
        )

    def has_runnable_nodes(self, graph: ExecutionGraph) -> bool:
        ready, _ = self.resolve(graph)
        return bool(ready)
