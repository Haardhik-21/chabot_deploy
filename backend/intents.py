"""Lightweight intent detection helpers to keep ask.py short."""

def is_greeting(q: str) -> bool:
    ql = (q or "").lower().strip()
    return any(kw in ql for kw in [
        "hi", "hello", "hey", "good morning", "good evening", "good afternoon"
    ])


def is_help(q: str) -> bool:
    ql = (q or "").lower().strip()
    return "help" in ql or ql in {"?", "how to", "what can you do", "i need help"}


def is_definition_question(q: str) -> bool:
    ql = (q or "").lower().strip()
    if ql.startswith("define "):
        return True
    if ql.startswith("what is "):
        # Exclude common "about" phrasings which are better treated as summaries
        about_phrases = [
            "what is it about",
            "what is this about",
            "what is the url about",
            "what is this document about",
            "what is the document about",
        ]
        if any(ql.startswith(p) or ql == p for p in about_phrases):
            return False
        return True
    return False


def is_smalltalk(q: str) -> bool:
    ql = (q or "").lower().strip()
    smalltalk = [
        "how are you", "are you there", "thank you", "thanks", "ok", "okay",
        "yo", "sup", "what's up", "whats up"
    ]
    return any(kw in ql for kw in smalltalk)


def is_about_question(q: str) -> bool:
    ql = (q or "").lower().strip()
    patterns = [
        "what is it about",
        "what is this about",
        "what is the url about",
        "what is this document about",
        "what is the document about",
        "what is this file about",
        "what is it",
        "give me an overview",
        "overview",
        "summarize",
        "summary",
    ]
    return any(ql == p or ql.startswith(p + " ") for p in patterns)
