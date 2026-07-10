import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from langgraph.graph.state import CompiledStateGraph

from app.agent_runtime.checkpoint.manager import CheckpointManager, InMemoryCheckpointManager
from app.agent_runtime.exceptions import GraphExecutionError
from app.agent_runtime.graph.builder import GraphBuilder
from app.agent_runtime.graph.edges import wire_default_workflow, wire_executive_workflow
from app.agent_runtime.graph.nodes import FinishNode, InputNode
from app.agent_runtime.state.models import AgentState, create_initial_state
from app.agents.executive.agent import ExecutiveAgent
from app.agents.executive.node import DecisionNode, ExecutiveAgentNode
from app.context.builder import ContextBuilder, ContextBuilderNode, create_context_builder
from app.llm.gateway import LLMGateway, create_llm_gateway
from app.skills.registry import CapabilityRegistry, create_capability_registry
from app.skills.resolver import SkillResolverNode

logger = logging.getLogger(__name__)


def build_default_graph(checkpoint_manager: CheckpointManager | None = None) -> CompiledStateGraph:
    """Build the demo workflow: START → process_input → finish → END."""
    builder = GraphBuilder()
    builder.add_node(InputNode())
    builder.add_node(FinishNode())
    wire_default_workflow(builder)
    return builder.build(checkpoint_manager=checkpoint_manager)


def build_executive_graph(
    llm_gateway: LLMGateway,
    context_builder: ContextBuilder | None = None,
    capability_registry: CapabilityRegistry | None = None,
    checkpoint_manager: CheckpointManager | None = None,
) -> CompiledStateGraph:
    """Build executive workflow with context, skills, and decision nodes."""
    registry = capability_registry or create_capability_registry()
    agent = ExecutiveAgent(llm_gateway, capability_registry=registry)
    builder_instance = context_builder or create_context_builder()
    builder = GraphBuilder()
    builder.add_node(InputNode())
    builder.add_node(ContextBuilderNode(builder_instance))
    builder.add_node(ExecutiveAgentNode(agent))
    builder.add_node(SkillResolverNode(registry))
    builder.add_node(DecisionNode())
    builder.add_node(FinishNode())
    wire_executive_workflow(builder)
    return builder.build(checkpoint_manager=checkpoint_manager)


def create_agent_runtime(
    checkpoint_manager: CheckpointManager | None = None,
    llm_gateway: LLMGateway | None = None,
    context_builder: ContextBuilder | None = None,
    capability_registry: CapabilityRegistry | None = None,
) -> "AgentRuntime":
    manager = checkpoint_manager or InMemoryCheckpointManager()
    gateway = llm_gateway or create_llm_gateway()
    graph = build_executive_graph(
        checkpoint_manager=manager,
        llm_gateway=gateway,
        context_builder=context_builder,
        capability_registry=capability_registry,
    )
    return AgentRuntime(graph=graph, checkpoint_manager=manager)


class AgentRuntime:
    """LangGraph runtime: executes workflows without business logic."""

    def __init__(
        self,
        graph: CompiledStateGraph,
        checkpoint_manager: CheckpointManager,
    ) -> None:
        self._graph = graph
        self._checkpoint_manager = checkpoint_manager

    async def execute(
        self,
        user_input: str,
        *,
        trace_id: str | None = None,
        context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentState:
        execution_id = uuid.uuid4().hex
        trace_id = trace_id or uuid.uuid4().hex[:16]
        state = create_initial_state(
            execution_id=execution_id,
            trace_id=trace_id,
            user_input=user_input,
            context=context,
            metadata=metadata,
        )

        logger.info(
            "graph execution started | execution_id=%s trace_id=%s status=started",
            execution_id,
            trace_id,
        )

        config = {"configurable": {"thread_id": execution_id}}

        try:
            result = await self._graph.ainvoke(state, config)
            final_state = _ensure_agent_state(result)
            self._checkpoint_manager.save(execution_id, final_state)
            logger.info(
                "graph execution completed | execution_id=%s trace_id=%s status=%s",
                execution_id,
                trace_id,
                final_state.get("status", "unknown"),
            )
            return final_state
        except Exception as exc:
            logger.error(
                "graph execution failed | execution_id=%s trace_id=%s status=failed error=%s",
                execution_id,
                trace_id,
                exc,
            )
            raise GraphExecutionError(f"Workflow execution failed: {exc}") from exc

    async def stream(
        self,
        user_input: str,
        *,
        trace_id: str | None = None,
        context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        execution_id = uuid.uuid4().hex
        trace_id = trace_id or uuid.uuid4().hex[:16]
        state = create_initial_state(
            execution_id=execution_id,
            trace_id=trace_id,
            user_input=user_input,
            context=context,
            metadata=metadata,
        )

        logger.info(
            "graph stream started | execution_id=%s trace_id=%s status=started",
            execution_id,
            trace_id,
        )

        config = {"configurable": {"thread_id": execution_id}}

        try:
            async for event in self._graph.astream(state, config, stream_mode="updates"):
                yield event
        except Exception as exc:
            logger.error(
                "graph stream failed | execution_id=%s trace_id=%s status=failed error=%s",
                execution_id,
                trace_id,
                exc,
            )
            raise GraphExecutionError(f"Workflow stream failed: {exc}") from exc


def _ensure_agent_state(result: Any) -> AgentState:
    if isinstance(result, dict):
        return AgentState(**result)
    raise GraphExecutionError("Graph returned unexpected state type")
