import logging
from collections.abc import Callable, Coroutine
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent_runtime.checkpoint.manager import CheckpointManager
from app.agent_runtime.exceptions import GraphBuildError
from app.agent_runtime.graph.nodes import BaseNode
from app.agent_runtime.state.models import AgentState

logger = logging.getLogger(__name__)

GraphNode = BaseNode | Callable[..., dict[str, Any] | Coroutine[Any, Any, dict[str, Any]]]


class GraphBuilder:
    """Builds and compiles LangGraph workflows from nodes and edges."""

    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: list[tuple[Any, Any]] = []
        self._conditional_edges: list[tuple[Any, Callable[[AgentState], str], dict[str, Any]]] = []

    def add_node(self, node: GraphNode) -> "GraphBuilder":
        name = node.name if isinstance(node, BaseNode) else getattr(node, "name", None)
        if not name:
            raise GraphBuildError("Node must have a name attribute")
        if name in self._nodes:
            raise GraphBuildError(f"Node already registered: {name}")
        self._nodes[name] = node
        return self

    def add_edge(self, source: Any, target: Any) -> "GraphBuilder":
        self._edges.append((source, target))
        return self

    def add_conditional_edges(
        self,
        source: Any,
        path: Callable[[AgentState], str],
        path_map: dict[str, Any],
    ) -> "GraphBuilder":
        self._conditional_edges.append((source, path, path_map))
        return self

    def build(self, checkpoint_manager: CheckpointManager | None = None) -> CompiledStateGraph:
        if not self._nodes:
            raise GraphBuildError("Cannot compile graph without nodes")

        graph = StateGraph(AgentState)

        for name, node in self._nodes.items():
            graph.add_node(name, node)

        if not self._edges and not self._conditional_edges:
            raise GraphBuildError("Cannot compile graph without edges")

        for source, target in self._edges:
            graph.add_edge(source, target)

        for source, path, path_map in self._conditional_edges:
            graph.add_conditional_edges(source, path, path_map)

        checkpointer = checkpoint_manager.get_checkpointer() if checkpoint_manager else None

        try:
            compiled = graph.compile(checkpointer=checkpointer)
        except Exception as exc:
            raise GraphBuildError(f"Graph compilation failed: {exc}") from exc

        logger.info(
            "graph compiled | nodes=%s edges=%s conditional_edges=%s checkpointing=%s",
            list(self._nodes.keys()),
            len(self._edges),
            len(self._conditional_edges),
            checkpointer is not None,
        )
        return compiled
