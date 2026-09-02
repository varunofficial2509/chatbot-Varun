"""Owner-only: manage the RAG knowledge base. Not linked from primary navigation."""

import logging

import streamlit as st

from app import config as settings
from app.rag.ingestion import IngestionError, ingest_file, save_uploaded_file, sync_knowledge_base
from app.rag.vectorstore import get_vectorstore
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
        if settings.KNOWLEDGE_DIR.joinpath(saved_name).suffix.lower() in {".pdf", ".md"}:
            result = ingest_file(settings.KNOWLEDGE_DIR / saved_name)
            _status(f"Indexed {saved_name} ({result['chunks_indexed']} chunks).", ok=True)
        else:
            _status(f"Saved {saved_name}.", ok=True)
    except IngestionError as exc:
        _status(str(exc), ok=False)
    except Exception:
        logger.exception("Failed to save/ingest uploaded knowledge file")
        _status("Failed to process document.", ok=False)

st.markdown("**Current knowledge**")
indexed = get_vectorstore().indexed_documents()
if indexed:
    items = "".join(
        f"<li>{name} <span class='text-faint'>({info['chunk_count']} chunks)</span></li>"
        for name, info in sorted(indexed.items())
    )
    st.html(f'<ul class="text-muted" style="font-size: 0.9rem;">{items}</ul>')
else:
    st.html('<span class="text-muted">No documents indexed yet.</span>')

if st.button("Sync Knowledge Base"):
    with st.spinner("Syncing..."):
        try:
            result = sync_knowledge_base()
            if result["documents_indexed"]:
                _status(
                    f"Indexed {result['documents_indexed']} new document(s) found in data/knowledge/ "
                    f"({result['chunks_indexed']} chunks).",
                    ok=True,
                )
            else:
                _status("Nothing new to index.", ok=True)
        except IngestionError as exc:
            _status(str(exc), ok=False)
        except Exception:
            logger.exception("Failed to sync knowledge base")
            _status("Failed to process document.", ok=False)

st.html('<hr style="margin: 1.5rem 0 0.75rem; opacity: 0.4;" />')
st.page_link("pages/chat.py", label="← Back to site")
