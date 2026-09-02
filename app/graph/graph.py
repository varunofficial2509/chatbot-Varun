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


def stream_graph(question: str, chat_history: list[dict], profile: dict, sources_out: list | None = None):
    """Yield the answer as it's generated, token by token.

    Uses stream_mode=["updates", "messages"] so the underlying chat model's
    tokens are surfaced as they're produced (without changing how
    generate_answer calls the LLM -- LangGraph streams any chat model
    invoked inside a node automatically), while "updates" lets us also
    catch retrieve_context's output as soon as that node finishes -- always
    before generate_answer starts streaming, since the graph runs them in
    that order. If sources_out is given, it's extended in place with the
    retrieved chunks so the caller can read it once the generator (a plain
    list, not a return value, since this is a generator function) has been
    fully consumed, e.g. by st.write_stream.
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
    for mode, chunk in compiled.stream(inputs, stream_mode=["updates", "messages"], config=config):
        if mode == "updates":
            update = chunk.get("retrieve_context")
            if update and sources_out is not None:
                sources_out.extend(update.get("retrieved_context", []))
        elif mode == "messages":
            message_chunk, metadata = chunk
            if metadata.get("langgraph_node") == "generate_answer" and message_chunk.text:
                yield message_chunk.text
