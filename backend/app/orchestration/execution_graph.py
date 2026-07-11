from uuid import UUID

from app.orchestration.models import ExecutionGraph, ExecutionGraphNode, NodeStatus
from app.planning.models import TaskPlan


def build_execution_graph(plan: TaskPlan) -> ExecutionGraph:
    """Convert a TaskPlan into a dynamic ExecutionGraph."""
    graph = ExecutionGraph(
        plan_id=plan.id,
        goal=plan.goal,
    )

    for step in plan.steps:
        node_id = str(step.id)
        graph.nodes[node_id] = ExecutionGraphNode(
            id=step.id,
            capability=step.capability,
            description=step.description,
            dependencies=list(step.dependencies),
            metadata={"plan_step_id": str(step.id)},
        )
        for dep_id in step.dependencies:
            graph.edges.append((str(dep_id), node_id))

    graph.execution_order = _topological_order(graph)
    return graph


def _topological_order(graph: ExecutionGraph) -> list[str]:
    ordered: list[str] = []
    remaining = list(graph.nodes.keys())
    completed: set[str] = set()

    while remaining:
        progress = False
        for node_id in list(remaining):
            node = graph.nodes[node_id]
            if all(str(dep) in completed for dep in node.dependencies):
                ordered.append(node_id)
                completed.add(node_id)
                remaining.remove(node_id)
                progress = True
        if not progress:
            ordered.extend(remaining)
            break

    return ordered


def sync_node_from_plan_step(graph: ExecutionGraph, step_id: UUID, *, status: NodeStatus, result: dict | None = None, error: str | None = None) -> None:
    node_id = str(step_id)
    if node_id not in graph.nodes:
        return
    node = graph.nodes[node_id]
    node.status = status
    if result is not None:
        node.result = result
    if error is not None:
        node.error = error
