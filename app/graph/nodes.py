"""Node functions for the recruiter graph: retrieve_context -> generate_answer."""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.graph.prompts import SYSTEM_PROMPT, build_user_message
from app.graph.state import RecruiterState
from app.services.llm import get_llm
from app.rag.retrieval import retrieve_relevant_chunks


def retrieve_context(state: RecruiterState) -> dict:
    chunks = retrieve_relevant_chunks(state["question"])
    return {"retrieved_context": chunks}


def generate_answer(state: RecruiterState) -> dict:
    llm = get_llm()

    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    for turn in state.get("chat_history", []):
        if turn["role"] == "user":
            messages.append(HumanMessage(content=turn["content"]))
        else:
            messages.append(AIMessage(content=turn["content"]))

    messages.append(
        HumanMessage(
            content=build_user_message(
                question=state["question"],
                profile=state.get("profile", {}),
                retrieved_context=state.get("retrieved_context", []),
            )
        )
    )

    response = llm.invoke(messages)
    return {"answer": response.text}
