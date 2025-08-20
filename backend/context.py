"""Conversation context utilities.
Shared across modules to keep ask.py slim.
"""
from typing import List, Dict

# Module-level shared context
conversation_context: List[Dict[str, str]] = []


def add_to_context(question: str, context: str, sources: List[str]) -> None:
    conversation_context.append({
        "question": question,
        "context": context,
        "sources": ",".join(sources or []),
    })


def get_recent_context() -> str:
    return "\n".join(
        f"Previous Q: {item['question']}\nContext: {item['context'][:200]}..."
        for item in conversation_context[-2:]
    )


def clear_conversation_context() -> None:
    conversation_context.clear()


def has_recent_context() -> bool:
    return bool(conversation_context)
