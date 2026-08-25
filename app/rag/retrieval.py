"""Retrieval of the most relevant knowledge chunks for a recruiter question."""

from app.rag.vectorstore import get_vectorstore


def retrieve_relevant_chunks(question: str, top_k: int | None = None) -> list[str]:
    """Return up to top_k knowledge chunks most relevant to the question."""
    return get_vectorstore().search(question, top_k=top_k)
