"""Environment-based configuration. No secrets or personal data live here.

Reads values from process environment first, falling back to Streamlit
secrets (`st.secrets`) so the same variable names work both locally (.env)
and on Streamlit Community Cloud (secrets.toml) without renaming anything.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _get(key: str, default: str = "") -> str:
    if key in os.environ:
        return os.environ[key]
    try:
        import streamlit as st

        return str(st.secrets[key])
    except Exception:
        return default


BASE_DIR = Path(__file__).resolve().parent.parent

# LLM (Gemini)
LLM_MODEL = _get("LLM_MODEL", "")
GOOGLE_API_KEY = _get("GOOGLE_API_KEY", "")

# LangSmith / LangChain tracing (picked up automatically by langchain if set)
LANGCHAIN_TRACING_V2 = _get("LANGCHAIN_TRACING_V2", "false")
LANGCHAIN_API_KEY = _get("LANGCHAIN_API_KEY", "")
LANGCHAIN_PROJECT = _get("LANGCHAIN_PROJECT", "personal-recruiter-chatbot")

# Owner-only knowledge management gate
ADMIN_PASSWORD = _get("ADMIN_PASSWORD", "")

# RAG / vector store
CHROMA_PATH = _get("CHROMA_PATH", str(BASE_DIR / "data" / "vectorstore"))
CHROMA_COLLECTION = _get("CHROMA_COLLECTION", "resume")
EMBEDDING_MODEL = _get("EMBEDDING_MODEL", "gemini-embedding-001")
TOP_K = int(_get("TOP_K", "5"))
CHUNK_SIZE = int(_get("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(_get("CHUNK_OVERLAP", "100"))

# Knowledge storage
KNOWLEDGE_DIR = BASE_DIR / "data" / "knowledge"
PROFILE_PATH = _get("PROFILE_PATH", str(KNOWLEDGE_DIR / "profile.json"))

# Upload limits
MAX_UPLOAD_SIZE_BYTES = int(_get("MAX_UPLOAD_SIZE_BYTES", str(10 * 1024 * 1024)))
ALLOWED_KNOWLEDGE_EXTENSIONS = {".pdf", ".md", ".json"}

# Propagate LangSmith env vars so LangChain's tracer (which reads os.environ
# directly) sees them even when they only came from Streamlit secrets.
for _key in ("LANGCHAIN_TRACING_V2", "LANGCHAIN_API_KEY", "LANGCHAIN_PROJECT"):
    if _key not in os.environ:
        os.environ[_key] = globals()[_key]
