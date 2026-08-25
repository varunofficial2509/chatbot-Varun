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


def stream_graph(question: str, chat_history: list[dict], profile: dict):
    """Yield the answer as it's generated, token by token.

    Uses stream_mode="messages" so the underlying chat model's tokens are
    surfaced as they're produced, without changing how generate_answer
    calls the LLM (LangGraph streams any chat model invoked inside a node
    automatically). Filtered to the generate_answer node so retrieval
    doesn't emit anything here.
    """
    compiled = build_graph()
    inputs = {
        "question": question,
        "chat_history": chat_history,
        "profile": profile,
        "retrieved_context": [],
        "answer": "",
    }
    config = {
        "tags": ["recruiter-chat"],
        "metadata": {"project": settings.LANGCHAIN_PROJECT},
    }
    for message_chunk, metadata in compiled.stream(inputs, stream_mode="messages", config=config):
        if metadata.get("langgraph_node") == "generate_answer" and message_chunk.text:
            yield message_chunk.text
