"""Vector store access, isolated behind a small add_documents/search interface.

Chroma is the only thing that knows about Chroma. Callers (ingestion,
retrieval) never touch the client or collection directly, so the storage
backend can be swapped later without touching the rest of the app.
"""

import hashlib

import chromadb
import streamlit as st
from chromadb.api.models.Collection import Collection

from app import config as settings
from app.rag.embeddings import get_embedding_function


@st.cache_resource(show_spinner=False)
def _get_client() -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=settings.CHROMA_PATH)


def _get_collection() -> Collection:
    return _get_client().get_or_create_collection(
        name=settings.CHROMA_COLLECTION,
        embedding_function=get_embedding_function(),
    )


class VectorStore:
    """Thin wrapper around the resume-chunk collection."""

    def count(self) -> int:
        return _get_collection().count()

    def clear(self) -> None:
        try:
            _get_client().delete_collection(name=settings.CHROMA_COLLECTION)
        except ValueError:
            pass  # collection doesn't exist yet

    def add_documents(self, documents: list[str], source: str) -> int:
        """Embed and store chunks, tagging each with its source filename."""
        if not documents:
            return 0
        collection = _get_collection()
        ids = [
            f"{source}-{i}-{hashlib.sha256(c.encode('utf-8')).hexdigest()[:16]}"
            for i, c in enumerate(documents)
        ]
        metadatas = [{"source": source, "chunk_index": i} for i in range(len(documents))]
        collection.add(documents=documents, ids=ids, metadatas=metadatas)
        return len(documents)

    def search(self, query: str, top_k: int | None = None) -> list[str]:
        collection = _get_collection()
        count = collection.count()
        if count == 0:
            return []
        k = min(top_k or settings.TOP_K, count)
        results = collection.query(query_texts=[query], n_results=k)
        documents = results.get("documents") or [[]]
        return documents[0]


@st.cache_resource(show_spinner=False)
def get_vectorstore() -> VectorStore:
    return VectorStore()
