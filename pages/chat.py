"""Standalone AI assistant page: the chatbot's own product surface.

app/ui/chat.py's render_chat_drawer() renders the conversation as a
collapsible slide-in panel meant to be embedded inside the portfolio's
home page. This project has no portfolio page to embed into, so this is
a plain full-page layout instead -- same underlying RAG/LangGraph call
(run_graph) and grounding data (profile_store), just without the drawer
chrome (open/close toggle, fixed positioning, slide transform).
"""

import logging

import streamlit as st

from app.graph.graph import stream_graph
from app.graph.prompts import NO_KNOWLEDGE_BASE_MESSAGE
from app.rag.profile_store import has_profile, load_profile
from app.ui.theme import inject_css

logger = logging.getLogger("recruiter_bot.chat_page")

MAX_HISTORY_TURNS = 20

SUGGESTIONS = [
    "Tell me about your Java experience",
    "What GenAI projects have you built?",
    "Explain your AeroWebb experience",
    "What is your experience with Kafka?",
]

inject_css()

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

if "messages" not in st.session_state:
    st.session_state.messages = []

rag_profile = load_profile()

if not st.session_state.messages:
    clicked = None
    with st.container(key="vt_suggestions"):
        for i, suggestion in enumerate(SUGGESTIONS):
            if st.button(suggestion, key=f"suggestion_{i}", use_container_width=True):
                clicked = suggestion
    if clicked:
        st.session_state.messages.append({"role": "user", "content": clicked})
        st.rerun()
else:
    for turn in st.session_state.messages:
        with st.chat_message(turn["role"]):
            st.markdown(turn["content"])

if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    with st.chat_message("assistant"):
        if not has_profile():
            answer = NO_KNOWLEDGE_BASE_MESSAGE
            st.markdown(answer)
        else:
            try:
                answer = st.write_stream(
                    stream_graph(
                        question=st.session_state.messages[-1]["content"],
                        chat_history=st.session_state.messages[:-1],
                        profile=rag_profile,
                    )
                )
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

st.html('<hr style="margin: 1.5rem 0 0.75rem; opacity: 0.4;" />')
st.page_link("pages/admin.py", label="Manage knowledge →")
