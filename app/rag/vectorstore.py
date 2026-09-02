"""Vector store access, isolated behind a small add_documents/search interface.

Chroma is the only thing that knows about Chroma. Callers (ingestion,
retrieval) never touch the client or collection directly, so the storage
backend can be swapped later without touching the rest of the app.
"""

import hashlib
from datetime import datetime, timezone

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

    def add_documents(self, documents: list[str], source: str, doc_hash: str) -> int:
        """Embed and store chunks, tagging each with its source filename, position,
        the source document's content hash, and when it was indexed."""
        if not documents:
            return 0
        collection = _get_collection()
        ingested_at = datetime.now(timezone.utc).isoformat()
        ids = [
            f"{source}-{i}-{hashlib.sha256(c.encode('utf-8')).hexdigest()[:16]}"
            for i, c in enumerate(documents)
        ]
        metadatas = [
            {
                "source": source,
                "chunk_index": i,
                "doc_hash": doc_hash,
                "ingested_at": ingested_at,
            }
            for i in range(len(documents))
        ]
        collection.add(documents=documents, ids=ids, metadatas=metadatas)
        return len(documents)

    def delete_by_source(self, source: str) -> None:
        """Purge every chunk belonging to one source document."""
        collection = _get_collection()
        if collection.count() == 0:
            return
        collection.delete(where={"source": source})

    def indexed_documents(self) -> dict[str, dict]:
        """Per-source summary of what's currently indexed: {source: {doc_hash, chunk_count}}.

        Used to skip re-embedding unchanged files and to drive the admin UI's
        document listing.
        """
        collection = _get_collection()
        if collection.count() == 0:
            return {}
        result = collection.get(include=["metadatas"])
        summary: dict[str, dict] = {}
        for meta in result.get("metadatas") or []:
            if not meta or "source" not in meta:
                continue
            entry = summary.setdefault(meta["source"], {"doc_hash": meta.get("doc_hash", ""), "chunk_count": 0})
            entry["chunk_count"] += 1
        return summary

    def search(self, query: str, top_k: int | None = None) -> list[dict]:
        """Return up to top_k chunks, each with its source document and a
        0-1 relevance score (higher is more relevant), for both grounding
        the answer and showing retrieval transparency in the UI."""
        collection = _get_collection()
        count = collection.count()
        if count == 0:
            return []
        k = min(top_k or settings.TOP_K, count)
        results = collection.query(
            query_texts=[query],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )
        documents = (results.get("documents") or [[]])[0]
        metadatas = (results.get("metadatas") or [[]])[0]
        distances = (results.get("distances") or [[]])[0]
        return [
            {
                "content": document,
                "source": (metadata or {}).get("source", "unknown"),
                # Chroma returns a distance, not a similarity; this maps it
                # onto a 0-1 scale (1 = identical) regardless of the
                # underlying distance metric, for a consistent UI score.
                "score": round(1 / (1 + distance), 3),
            }
            for document, metadata, distance in zip(documents, metadatas, distances)
        ]


@st.cache_resource(show_spinner=False)
def get_vectorstore() -> VectorStore:
    return VectorStore()
