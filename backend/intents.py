"""Lightweight intent detection helpers to keep ask.py short."""

import re

def _has_word(ql: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", ql) is not None

def _has_phrase(ql: str, phrase: str) -> bool:
    return re.search(rf"\b{re.escape(phrase)}\b", ql) is not None

def is_greeting(q: str) -> bool:
    ql = (q or "").lower().strip()
    single_words = ["hi", "hello", "hey"]
    phrases = ["good morning", "good evening", "good afternoon"]
    return any(_has_word(ql, w) for w in single_words) or any(_has_phrase(ql, p) for p in phrases)


def is_help(q: str) -> bool:
    ql = (q or "").lower().strip()
    return (
        _has_word(ql, "help")
        or ql in {"?", "how to", "what can you do", "i need help"}
    )


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
    phrases = [
        "how are you", "are you there", "thank you", "thanks",
        "what's up", "whats up"
    ]
    words = ["ok", "okay", "yo", "sup"]
    return any(_has_phrase(ql, p) for p in phrases) or any(_has_word(ql, w) for w in words)


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


def is_entertainment_question(q: str) -> bool:
    """Basic detector for entertainment-related questions."""
    ql = (q or "").lower().strip()
    keywords = [
        "movie", "film", "cinema", "actor", "actress", "director", "producer", "celebrity",
        "bollywood", "tollywood", "hollywood", "ott", "series", "tv show", "song", "music",
        "box office", "trailer", "release date", "imdb", "rotten tomatoes",
        "sekhar kammula", "kammula", "rajamouli", "ntr", "allu arjun", "deepika", "prabhas",
        "cast", "starring", "soundtrack"
    ]
    if any(k in ql for k in keywords):
        return True
    # Regex patterns for common verb/noun variations
    import re
    patterns = [
        r"\bdirect(?:or|ed|ing)\b",
        r"\breleas(?:e|ed|ing)\b",
        r"\bstar(?:s|ring)?\b",
        r"\bbox\s+office\b",
        r"\btv\s*show\b",
        r"\bseries\b",
    ]
    return any(re.search(p, ql) for p in patterns)
