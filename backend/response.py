from typing import List, Dict

from qa_core import answer_question_stream

SOURCES_MARKER = "\n\nSources:\n"


def split_compound(question: str) -> List[str]:
    parts = [p.strip() for p in (question or "").split("?")]
    subs = [p for p in parts if len(p.split()) >= 3]
    return [s + "?" for s in subs] if subs else [question]


def collect_full_answer(question: str) -> Dict[str, str]:
    chunks: List[str] = []
    for ch in answer_question_stream(question):
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


def generate_streaming_response(question: str):
    subs = split_compound(question)
    # Single-question: stream answer but suppress separate "Sources:" block
    if len(subs) <= 1:
        for chunk in answer_question_stream(question):
            if not chunk:
                continue
            text = chunk
            if SOURCES_MARKER in text:
                before = text.split(SOURCES_MARKER, 1)[0].replace("data: ", "")
                if before.strip():
                    yield before + "\n"
                break
            yield text.replace("data: ", "")
        return

    # Compound: answer each sub-question fully, then stream concise lines
    for idx, sq in enumerate(subs, start=1):
        result = collect_full_answer(sq)
        ans_line = f"{idx}) {result['answer'].rstrip()}"
        if ans_line:
            yield ans_line + "\n"
        if idx != len(subs):
            yield "\n"
