"""Streamlit entrypoint for the standalone AI assistant project."""

import streamlit as st

from app.rag.ingestion import ensure_knowledge_base
from app.ui.theme import configure_page

configure_page("Varun Teja Jaladhula — AI Assistant")

ensure_knowledge_base()

pages = [
    st.Page("pages/chat.py", title="AI Assistant", url_path="chat", default=True),
    st.Page("pages/admin.py", title="Manage Knowledge", url_path="admin", visibility="hidden"),
]

nav = st.navigation(pages, position="hidden")
nav.run()
