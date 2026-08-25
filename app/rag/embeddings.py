"""Gemini embedding function used for both ingestion and retrieval."""

import chromadb.utils.embedding_functions as embedding_functions
import streamlit as st
from chromadb.api.types import Documents, Embeddings

from app import config as settings


class _GeminiEmbeddingFunction(embedding_functions.EmbeddingFunction):
    """Adapts langchain's Gemini embeddings to Chroma's EmbeddingFunction protocol."""

    def __init__(self, model: str, api_key: str):
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        self._embeddings = GoogleGenerativeAIEmbeddings(model=model, google_api_key=api_key)

    def __call__(self, input: Documents) -> Embeddings:
        return self._embeddings.embed_documents(list(input))


@st.cache_resource(show_spinner=False)
def get_embedding_function() -> embedding_functions.EmbeddingFunction:
    if not settings.GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY is not set")
    return _GeminiEmbeddingFunction(model=settings.EMBEDDING_MODEL, api_key=settings.GOOGLE_API_KEY)
