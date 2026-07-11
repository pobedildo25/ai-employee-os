from datetime import datetime

from app.orchestration.models import ExecutionGraph, ExecutionGraphNode, NodeStatus


class Scheduler:
    """Schedule ready nodes for parallel execution and track statuses."""

    def mark_running(self, graph: ExecutionGraph, nodes: list[ExecutionGraphNode]) -> list[str]:
        running_ids: list[str] = []
        for node in nodes:
            node_id = str(node.id)
            if node_id not in graph.nodes:
                continue
            graph.nodes[node_id].status = NodeStatus.RUNNING
            running_ids.append(node_id)
        return running_ids

    def mark_completed(self, graph: ExecutionGraph, node_id: str, result: dict | None = None) -> None:
        node = graph.nodes[node_id]
        node.status = NodeStatus.COMPLETED
        node.result = result
        node.error = None

    def mark_failed(self, graph: ExecutionGraph, node_id: str, error: str) -> None:
        node = graph.nodes[node_id]
        node.status = NodeStatus.FAILED
        node.error = error

    def mark_cancelled(self, graph: ExecutionGraph) -> list[str]:
        cancelled: list[str] = []
        for node_id, node in graph.nodes.items():
            if node.status in {NodeStatus.WAITING, NodeStatus.READY, NodeStatus.PAUSED}:
                node.status = NodeStatus.CANCELLED
                cancelled.append(node_id)
        return cancelled

    def mark_paused(self, graph: ExecutionGraph) -> list[str]:
        paused: list[str] = []
        for node_id, node in graph.nodes.items():
            if node.status in {NodeStatus.WAITING, NodeStatus.READY}:
                node.status = NodeStatus.PAUSED
                paused.append(node_id)
        return paused

    def resume_paused(self, graph: ExecutionGraph) -> None:
        for node in graph.nodes.values():
            if node.status == NodeStatus.PAUSED:
                node.status = NodeStatus.WAITING

    def snapshot_statuses(self, graph: ExecutionGraph) -> dict[str, str]:
        return {node_id: node.status.value for node_id, node in graph.nodes.items()}

    def touch(self, graph: ExecutionGraph) -> datetime:
        return datetime.now()
