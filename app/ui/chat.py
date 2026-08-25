"""Chat rendering: message history, suggestion chips, and the right-side drawer panel."""

import logging

import streamlit as st

from app.graph.graph import run_graph
from app.graph.prompts import NO_KNOWLEDGE_BASE_MESSAGE
from app.rag.profile_store import has_profile, load_profile

logger = logging.getLogger("recruiter_bot.chat")

MAX_HISTORY_TURNS = 20

SUGGESTIONS = [
    "Tell me about your Java experience",
    "What GenAI projects have you built?",
    "Explain your AeroWebb experience",
    "What is your experience with Kafka?",
]


def render_history(messages: list[dict]) -> None:
    for turn in messages:
        with st.chat_message(turn["role"]):
            st.markdown(turn["content"])


def render_empty_state() -> str | None:
    """Shows the intro + suggestion chips. Returns the clicked suggestion, if any."""
    st.html(
        """
        <div class="vt-ai-hero">
            <div class="vt-ai-hero-title">Ask <span class="accent">Varun</span>.</div>
            <div class="vt-ai-hero-sub">
                An AI assistant grounded in my experience, projects and skills.
            </div>
        </div>
        """
    )

    clicked = None
    with st.container(key="vt_suggestions"):
        for i, suggestion in enumerate(SUGGESTIONS):
            if st.button(suggestion, key=f"suggestion_{i}", use_container_width=True):
                clicked = suggestion
    return clicked


def render_chat_drawer(is_open: bool) -> None:
    """Right-side slide-in chat overlay (see .st-key-vt_chat_drawer in
    theme.py). The outer container stays mounted every rerun so its CSS
    transform can animate open/closed; nothing inside is rendered while
    closed, so no RAG calls happen off-screen and the portfolio behind it
    is never touched.

    st.chat_input is a *sibling* of the scrollable history box (both
    direct children of vt_chat_drawer, not nested) — that's what makes
    Streamlit dock it to the bottom of the drawer itself rather than the
    whole app viewport (per st.chat_input's own "inline" docs example).
    """
    st.html(
        f"<style>.st-key-vt_chat_drawer {{ "
        f"transform: translateX({0 if is_open else 100}%); }}</style>"
    )

    with st.container(key="vt_chat_drawer"):
        if not is_open:
            return

        header_col, close_col = st.columns([5, 1])
        with header_col:
            st.html('<div class="vt-chat-drawer-title mono"><span class="accent">$</span> varun.ai</div>')
        with close_col:
            if st.button("✕", key="vt_chat_close"):
                st.session_state.chat_drawer_open = False
                st.rerun()

        if "messages" not in st.session_state:
            st.session_state.messages = []

        rag_profile = load_profile()

        with st.container(key="vt_chat_scroll", height=480, border=False):
            if not st.session_state.messages:
                suggestion = render_empty_state()
                if suggestion:
                    st.session_state.messages.append({"role": "user", "content": suggestion})
                    st.rerun()
            else:
                render_history(st.session_state.messages)

            # The last turn is a user message awaiting a response (either
            # just typed via chat_input below, or just appended above
            # before the rerun) — generate and show the answer now.
            if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
                with st.chat_message("assistant"):
                    if not has_profile():
                        answer = NO_KNOWLEDGE_BASE_MESSAGE
                    else:
                        with st.spinner("Thinking..."):
                            try:
                                result = run_graph(
                                    question=st.session_state.messages[-1]["content"],
                                    chat_history=st.session_state.messages[:-1],
                                    profile=rag_profile,
                                )
                                answer = result["answer"]
                            except Exception:
                                logger.exception("Chat request failed")
                                answer = (
                                    "Sorry, I ran into a problem answering that just now. "
                                    "Please try again in a moment."
                                )
                    st.markdown(answer)

                st.session_state.messages.append({"role": "assistant", "content": answer})
                del st.session_state.messages[: max(0, len(st.session_state.messages) - MAX_HISTORY_TURNS)]

        question = st.chat_input("Ask anything about my experience...")
        if question:
            st.session_state.messages.append({"role": "user", "content": question})
            st.rerun()
