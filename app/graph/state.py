"""State passed between nodes in the recruiter graph."""

from typing import TypedDict


class ChatTurn(TypedDict):
    role: str  # "user" or "assistant"
    content: str


class RecruiterState(TypedDict):
    question: str
    chat_history: list[ChatTurn]
    profile: dict
    retrieved_context: list[str]
    answer: str
