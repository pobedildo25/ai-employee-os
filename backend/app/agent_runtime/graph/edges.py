from langgraph.graph import END, START

from app.agent_runtime.graph.builder import GraphBuilder
from app.agents.executive.node import EXECUTIVE_AGENT_NODE
from app.context.builder import CONTEXT_BUILDER_NODE
from app.document_creation.nodes.document_creation_node import DOCUMENT_CREATION_NODE
from app.document_creation.nodes.document_render_node import DOCUMENT_RENDER_NODE
from app.planning.nodes.executor_node import QUALITY_CHECK_NODE
from app.planning.nodes.planner_node import PLANNER_NODE
from app.skills.resolver import SKILL_RESOLVER_NODE

PROCESS_INPUT_NODE = "process_input"
FINISH_NODE = "finish"


def wire_default_workflow(builder: GraphBuilder) -> GraphBuilder:
    """Connect START → process_input → finish → END (demo workflow)."""
    builder.add_edge(START, PROCESS_INPUT_NODE)
    builder.add_edge(PROCESS_INPUT_NODE, FINISH_NODE)
    builder.add_edge(FINISH_NODE, END)
    return builder


def wire_executive_workflow(builder: GraphBuilder) -> GraphBuilder:
    """Connect full pipeline through document creation and rendering."""
    builder.add_edge(START, PROCESS_INPUT_NODE)
    builder.add_edge(PROCESS_INPUT_NODE, CONTEXT_BUILDER_NODE)
    builder.add_edge(CONTEXT_BUILDER_NODE, EXECUTIVE_AGENT_NODE)
    builder.add_edge(EXECUTIVE_AGENT_NODE, SKILL_RESOLVER_NODE)
    builder.add_edge(SKILL_RESOLVER_NODE, PLANNER_NODE)
    builder.add_edge(PLANNER_NODE, DOCUMENT_CREATION_NODE)
    builder.add_edge(DOCUMENT_CREATION_NODE, DOCUMENT_RENDER_NODE)
    builder.add_edge(DOCUMENT_RENDER_NODE, QUALITY_CHECK_NODE)
    builder.add_edge(QUALITY_CHECK_NODE, END)
    return builder
