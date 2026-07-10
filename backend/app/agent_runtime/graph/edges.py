from langgraph.graph import END, START

from app.agent_runtime.graph.builder import GraphBuilder
from app.agent_runtime.state.models import AgentState
from app.agents.executive.node import EXECUTIVE_AGENT_NODE
from app.context.builder import CONTEXT_BUILDER_NODE
from app.document_creation.nodes.document_creation_node import DOCUMENT_CREATION_NODE
from app.document_creation.nodes.document_render_node import DOCUMENT_RENDER_NODE
from app.planning.nodes.planner_node import PLANNER_NODE
from app.quality.nodes.quality_gate_node import QUALITY_GATE_NODE
from app.quality.models import ReviewStatus
from app.revision.nodes.revision_node import REVISION_NODE
from app.revision.policies.revision_policy import can_auto_revise
from app.skills.resolver import SKILL_RESOLVER_NODE

PROCESS_INPUT_NODE = "process_input"
FINISH_NODE = "finish"

ROUTE_PASS = "pass"
ROUTE_REVISE = "revise"
ROUTE_END = "end"


def route_after_quality(state: AgentState) -> str:
    """Route after quality gate: revise once automatically, otherwise end."""
    review = state.get("review_result") or {}
    status = review.get("status")
    revision_count = int(state.get("revision_count") or 0)

    if status == ReviewStatus.REVISE.value and can_auto_revise(revision_count):
        return ROUTE_REVISE
    return ROUTE_END


def wire_default_workflow(builder: GraphBuilder) -> GraphBuilder:
    """Connect START → process_input → finish → END (demo workflow)."""
    builder.add_edge(START, PROCESS_INPUT_NODE)
    builder.add_edge(PROCESS_INPUT_NODE, FINISH_NODE)
    builder.add_edge(FINISH_NODE, END)
    return builder


def wire_executive_workflow(builder: GraphBuilder) -> GraphBuilder:
    """Connect full pipeline with optional one-shot revision loop."""
    builder.add_edge(START, PROCESS_INPUT_NODE)
    builder.add_edge(PROCESS_INPUT_NODE, CONTEXT_BUILDER_NODE)
    builder.add_edge(CONTEXT_BUILDER_NODE, EXECUTIVE_AGENT_NODE)
    builder.add_edge(EXECUTIVE_AGENT_NODE, SKILL_RESOLVER_NODE)
    builder.add_edge(SKILL_RESOLVER_NODE, PLANNER_NODE)
    builder.add_edge(PLANNER_NODE, DOCUMENT_CREATION_NODE)
    builder.add_edge(DOCUMENT_CREATION_NODE, DOCUMENT_RENDER_NODE)
    builder.add_edge(DOCUMENT_RENDER_NODE, QUALITY_GATE_NODE)
    builder.add_conditional_edges(
        QUALITY_GATE_NODE,
        route_after_quality,
        {
            ROUTE_REVISE: REVISION_NODE,
            ROUTE_END: END,
            ROUTE_PASS: END,
        },
    )
    builder.add_edge(REVISION_NODE, QUALITY_GATE_NODE)
    return builder
