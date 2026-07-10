from langgraph.graph import END, START

from app.agent_runtime.graph.builder import GraphBuilder
from app.agents.executive.node import DECISION_NODE, EXECUTIVE_AGENT_NODE

PROCESS_INPUT_NODE = "process_input"
FINISH_NODE = "finish"


def wire_default_workflow(builder: GraphBuilder) -> GraphBuilder:
    """Connect START → process_input → finish → END (demo workflow)."""
    builder.add_edge(START, PROCESS_INPUT_NODE)
    builder.add_edge(PROCESS_INPUT_NODE, FINISH_NODE)
    builder.add_edge(FINISH_NODE, END)
    return builder


def wire_executive_workflow(builder: GraphBuilder) -> GraphBuilder:
    """Connect START → process_input → executive_agent → decision → finish → END."""
    builder.add_edge(START, PROCESS_INPUT_NODE)
    builder.add_edge(PROCESS_INPUT_NODE, EXECUTIVE_AGENT_NODE)
    builder.add_edge(EXECUTIVE_AGENT_NODE, DECISION_NODE)
    builder.add_edge(DECISION_NODE, FINISH_NODE)
    builder.add_edge(FINISH_NODE, END)
    return builder
