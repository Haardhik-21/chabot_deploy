from typing import List, Dict

from qa_core import answer_question_stream

SOURCES_MARKER = "\n\nSources:\n"


def split_compound(question: str) -> List[str]:
    parts = [p.strip() for p in (question or "").split("?")]
    subs = [p for p in parts if len(p.split()) >= 3]
    return [s + "?" for s in subs] if subs else [question]


def collect_full_answer(question: str, entertainment_enabled: bool = False) -> Dict[str, str]:
    chunks: List[str] = []
    for ch in answer_question_stream(question, entertainment_enabled=entertainment_enabled):
        if not ch:
            continue
        chunks.append(ch)
    full = "".join(chunks)
    ans, src = full, ""
    if SOURCES_MARKER in full:
        ans, src = full.split(SOURCES_MARKER, 1)
        ans = ans.strip()
        src = src.strip()
    return {"answer": ans, "sources": src}


def generate_streaming_response(question: str, entertainment_enabled: bool = False):
    subs = split_compound(question)
    # Single-question: stream full answer including the trailing Sources block
    if len(subs) <= 1:
        for chunk in answer_question_stream(question, entertainment_enabled=entertainment_enabled):
            if not chunk:
                continue
            yield chunk.replace("data: ", "")
        return

    # Compound: answer each sub-question fully, include its Sources, and stream concise lines
    for idx, sq in enumerate(subs, start=1):
        result = collect_full_answer(sq, entertainment_enabled=entertainment_enabled)
        ans_line = f"{idx}) {result['answer'].rstrip()}"
        if ans_line:
            yield ans_line + "\n"
        if result.get("sources"):
            yield "Sources:\n" + result["sources"] + "\n"
        if idx != len(subs):
            yield "\n"
