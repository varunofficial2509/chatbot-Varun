"""LangGraph pipeline: retrieve_context -> generate_answer.

Kept as an explicit two-node graph (rather than a single function) so each
stage is independently traceable in LangSmith and easy to extend later
(e.g. adding a query-rewriting node). LangSmith tracing is wired up purely
via environment variables and the run config below, so it can be enabled
later without changing this graph or the Streamlit UI that calls it.
"""

import streamlit as st
from langgraph.graph import StateGraph

from app import config as settings
from app.graph.edges import wire
from app.graph.nodes import generate_answer, retrieve_context
from app.graph.state import RecruiterState


@st.cache_resource(show_spinner=False)
def build_graph():
    graph = StateGraph(RecruiterState)
    graph.add_node("retrieve_context", retrieve_context)
    graph.add_node("generate_answer", generate_answer)
    wire(graph)
    return graph.compile()


def run_graph(question: str, chat_history: list[dict], profile: dict) -> RecruiterState:
    compiled = build_graph()
    return compiled.invoke(
        {
            "question": question,
            "chat_history": chat_history,
            "profile": profile,
            "retrieved_context": [],
            "answer": "",
        },
        config={
            "tags": ["recruiter-chat"],
            "metadata": {"project": settings.LANGCHAIN_PROJECT},
        },
    )
