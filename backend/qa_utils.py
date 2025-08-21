import re
from typing import List

# Abbreviation set for trimming logic
_ABBREV = {"mr.", "mrs.", "ms.", "dr.", "prof.", "sr.", "jr.", "vs.", "etc.", "e.g.", "i.e.", "inc.", "ltd.", "co.", "dept.", "univ."}


def extract_name_phrase(text: str) -> str:
    tl = (text or "").strip().lower()
    m = re.match(r"\s*(who\s+is|who's)\s+(.+)$", tl)
    if m:
        return m.group(2).strip()
    parts = [p for p in re.split(r"\s+", tl) if p]
    if 2 <= len(parts) <= 4:
        return " ".join(parts)
    return ""


def clean_model_chunk(t: str) -> str:
    # Remove boilerplate and source headings
    t = re.sub(r"(?im)^\s*(\*\*|__)?\s*important\s+reminder\s*:.*$", "", t)
    t = re.sub(r"(?im)^\s*(\*\*|__)?\s*sources?\s*:.*$", "", t)
    t = re.sub(r"(?im)^\s*-\s.*\.pdf.*$", "", t)
    t = re.sub(r"(?i)(for\s+educational\s+purposes\s+only|not\s+a\s+substitute\s+for\s+professional\s+medical\s+advice|consult\s+with\s+a\s+qualified\s+healthcare\s+provider)[^.]*\.?", "", t)
    # Strip Markdown bold/italics markers while keeping text
    t = re.sub(r"\*\*(.*?)\*\*", r"\1", t)
    t = re.sub(r"__(.*?)__", r"\1", t)
    t = re.sub(r"\*(.*?)\*", r"\1", t)
    t = re.sub(r"_(.*?)_", r"\1", t)
    # Normalize leading bullet markers to hyphens
    t = re.sub(r"(?m)^\s*[•▪●·]\s+", "- ", t)
    t = re.sub(r"(?m)^\s*\*\s+", "- ", t)
    # Collapse excessive blank lines
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def smart_trim(t: str, limit: int) -> str:
    if len(t) <= limit:
        return t
    snippet = t[:limit]
    tail = snippet[-220:]

    def _is_abbrev_before(text: str, pos: int) -> bool:
        look = text[max(0, pos - 8):pos + 1].lower()
        return any(look.endswith(a) for a in _ABBREV)

    for punct in [". ", "! ", "? "]:
        idx = tail.rfind(punct)
        if idx != -1:
            if punct.startswith(".") and _is_abbrev_before(tail, idx):
                continue
            cut = len(snippet) - len(tail) + idx + 1
            return snippet[:cut].rstrip()

    nl = snippet.rfind("\n")
    if nl != -1 and nl > limit * 0.6:
        candidate = snippet[:nl].rstrip()
        while candidate and candidate[-1] in ":,(":
            candidate = candidate[:-1].rstrip()
        return candidate

    sp = snippet.rfind(" ")
    if sp != -1 and sp > limit * 0.6:
        candidate = snippet[:sp].rstrip()
        while candidate and candidate[-1] in ":,(":
            candidate = candidate[:-1].rstrip()
        return candidate

    candidate = snippet.rstrip()
    while candidate and candidate[-1] in ":,(":
        candidate = candidate[:-1].rstrip()
    return candidate


def tidy_text(t: str) -> str:
    # Remove stray emphasis markers
    t = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", t)
    t = re.sub(r"_{1,2}([^_]+)_{1,2}", r"\1", t)
    # Normalize punctuation spacing
    t = re.sub(r"\s+([,.;:!?])", r"\1", t)
    t = re.sub(r"\(\s+\)", "()", t)
    t = re.sub(r"\s{2,}", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()
