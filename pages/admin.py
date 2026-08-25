"""Owner-only: manage the RAG knowledge base. Not linked from primary navigation."""

import logging

import streamlit as st

from app import config as settings
from app.rag.ingestion import (
    IngestionError,
    list_knowledge_files,
    rebuild_knowledge_base,
    save_uploaded_file,
)
from app.services import content
from app.ui import components
from app.ui.theme import inject_css

logger = logging.getLogger("recruiter_bot.admin")

inject_css()

profile_meta = content.load_profile()
components.render_nav_header(name=profile_meta.get("name", ""))


def _status(message: str, ok: bool) -> None:
    color = "var(--accent)" if ok else "var(--text)"
    st.html(f'<p style="color: {color}; font-size: 0.9rem;">{message}</p>')


if not settings.ADMIN_PASSWORD:
    st.html('<p class="text-muted">Set ADMIN_PASSWORD in your environment to manage knowledge.</p>')
    st.stop()

if not st.session_state.get("admin_unlocked"):
    st.html('<p class="text-muted">Owner access only.</p>')
    password = st.text_input("Password", type="password", key="admin_password_input")
    if st.button("Unlock", type="primary"):
        if password and password == settings.ADMIN_PASSWORD:
            st.session_state.admin_unlocked = True
            st.rerun()
        else:
            _status("Incorrect password.", ok=False)
    st.stop()

st.html(
    '<div style="font-size: 0.78rem; letter-spacing: 0.12em; text-transform: uppercase;" class="text-muted">'
    "Knowledge Base</div>"
)

uploaded = st.file_uploader("Upload document", type=["pdf", "md", "json"], key="knowledge_uploader")
if uploaded is not None and st.button("Upload"):
    try:
        saved_name = save_uploaded_file(uploaded.name, uploaded.getvalue())
        _status(f"Saved {saved_name}. Rebuild the knowledge base to apply it.", ok=True)
    except IngestionError as exc:
        _status(str(exc), ok=False)
    except Exception:
        logger.exception("Failed to save uploaded knowledge file")
        _status("Failed to process document.", ok=False)

st.markdown("**Current knowledge**")
files = list_knowledge_files()
if files:
    items = "".join(f"<li>{name}</li>" for name in files)
    st.html(f'<ul class="text-muted" style="font-size: 0.9rem;">{items}</ul>')
else:
    st.html('<span class="text-muted">No knowledge files yet.</span>')

if st.button("Rebuild Knowledge Base", type="primary"):
    with st.spinner("Rebuilding..."):
        try:
            result = rebuild_knowledge_base()
            _status(
                f"Knowledge added successfully "
                f"({result['chunks_indexed']} chunks from {result['documents_indexed']} documents).",
                ok=True,
            )
        except IngestionError as exc:
            _status(str(exc), ok=False)
        except Exception:
            logger.exception("Failed to rebuild knowledge base")
            _status("Failed to process document.", ok=False)

st.html('<hr style="margin: 1.5rem 0 0.75rem; opacity: 0.4;" />')
st.page_link("pages/chat.py", label="← Back to site")
