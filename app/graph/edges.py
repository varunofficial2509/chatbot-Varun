"""Edge wiring for the recruiter graph."""

from langgraph.graph import END, START
from langgraph.graph.state import StateGraph


def wire(graph: StateGraph) -> StateGraph:
    graph.add_edge(START, "retrieve_context")
    graph.add_edge("retrieve_context", "generate_answer")
    graph.add_edge("generate_answer", END)
    return graph
