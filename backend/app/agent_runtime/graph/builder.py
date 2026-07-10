import logging
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent_runtime.checkpoint.manager import CheckpointManager
from app.agent_runtime.exceptions import GraphBuildError
from app.agent_runtime.graph.nodes import BaseNode
from app.agent_runtime.state.models import AgentState

logger = logging.getLogger(__name__)


class GraphBuilder:
    """Builds and compiles LangGraph workflows from nodes and edges."""

    def __init__(self) -> None:
        self._nodes: dict[str, BaseNode] = {}
        self._edges: list[tuple[Any, Any]] = []

    def add_node(self, node: BaseNode) -> "GraphBuilder":
        if node.name in self._nodes:
            raise GraphBuildError(f"Node already registered: {node.name}")
        self._nodes[node.name] = node
        return self

    def add_edge(self, source: Any, target: Any) -> "GraphBuilder":
        self._edges.append((source, target))
        return self

    def build(self, checkpoint_manager: CheckpointManager | None = None) -> CompiledStateGraph:
        if not self._nodes:
            raise GraphBuildError("Cannot compile graph without nodes")

        graph = StateGraph(AgentState)

        for name, node in self._nodes.items():
            graph.add_node(name, node)

        if not self._edges:
            raise GraphBuildError("Cannot compile graph without edges")

        for source, target in self._edges:
            graph.add_edge(source, target)

        checkpointer = checkpoint_manager.get_checkpointer() if checkpoint_manager else None

        try:
            compiled = graph.compile(checkpointer=checkpointer)
        except Exception as exc:
            raise GraphBuildError(f"Graph compilation failed: {exc}") from exc

        logger.info(
            "graph compiled | nodes=%s edges=%s checkpointing=%s",
            list(self._nodes.keys()),
            len(self._edges),
            checkpointer is not None,
        )
        return compiled
