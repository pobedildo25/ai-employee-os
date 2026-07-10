from langgraph.graph import END, START

from app.agent_runtime.graph.builder import GraphBuilder

PROCESS_INPUT_NODE = "process_input"
FINISH_NODE = "finish"


def wire_default_workflow(builder: GraphBuilder) -> GraphBuilder:
    """Connect START → process_input → finish → END."""
    builder.add_edge(START, PROCESS_INPUT_NODE)
    builder.add_edge(PROCESS_INPUT_NODE, FINISH_NODE)
    builder.add_edge(FINISH_NODE, END)
    return builder
