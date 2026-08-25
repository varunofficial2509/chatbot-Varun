"""Gemini chat model, built once per process."""

import streamlit as st
from langchain_core.language_models.chat_models import BaseChatModel

from app import config as settings

DEFAULT_MODEL = "gemini-3.5-flash-lite"


@st.cache_resource(show_spinner=False)
def get_llm() -> BaseChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI

    if not settings.GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY is not set")
    return ChatGoogleGenerativeAI(
        model=settings.LLM_MODEL or DEFAULT_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        max_output_tokens=1024,
        temperature=0.3,
    )
