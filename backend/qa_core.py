
from typing import List, Dict, Any, Generator
import re
import traceback

from embedding import get_embedding
from gemini_client import get_streaming_answer
from intents import is_greeting, is_help, is_definition_question, is_smalltalk, is_about_question
from prompts import (
    get_greeting_response,
    get_help_response,
    get_context_prompt,
    get_definition_prompt,
    get_follow_up_prompt,
    get_summary_prompt,
)
from context import add_to_context, has_recent_context, get_recent_context
from vector_core import search_similar_chunks, search_web_chunks
from qutils import pages_by_source, format_sources_with_pages


def answer_question_stream(question: str) -> Generator[str, None, None]:
    try:
        q = (question or "").strip()
        if not q:
            yield "Please enter a question about your documents or ingested web pages."
            return

        # Greetings should never trigger retrieval; always reply politely
        if is_greeting(q):
            yield get_greeting_response(); return
        if is_help(q) and not has_recent_context():
            yield get_help_response(); return
        if is_smalltalk(q):
            ql = q.lower()
            if "thank you" in ql or "thanks" in ql:
                yield "You're welcome! If you have more questions about your documents or web sources, just ask. 😊"; return
            if ql in {"ok", "okay", "ok.", "okay."} or ql.startswith("ok ") or ql.startswith("okay "):
                yield "Got it. When you're ready, ask me about your uploaded PDFs or ingested web pages!"; return
            yield "I'm here and happy to help! Ask about your uploaded PDFs or ingested web pages. 😊"; return

        # No domain gating: answer from uploaded PDFs and ingested web pages.

        emb = get_embedding(q)
        terms = q.split()
        very_short = (len(terms) <= 2) or (len(q) <= 5)
        prefer_web = very_short or is_about_question(q)
        # Retrieval strategy: for about/very short questions, prefer web first with higher k
        if prefer_web:
            hits = search_web_chunks(emb, k=12)
            if not hits:
                hits = search_similar_chunks(emb, k=12)
        else:
            hits = search_similar_chunks(emb, k=10)
            if not hits:
                hits = search_web_chunks(emb, k=10)
        if not hits:
            yield "I couldn't find relevant information in the uploaded documents. Please try rephrasing."; return

        # Build context using ONLY the top-1 source by aggregate score to avoid unrelated source bleed-through
        score_by_source: Dict[str, float] = {}
        for it in hits:
            s = it.get("filename") or it.get("source") or "Document"
            score_by_source[s] = score_by_source.get(s, 0.0) + float(it.get("score", 0.0))
        top_sources = [s for s, _ in sorted(score_by_source.items(), key=lambda x: x[1], reverse=True)[:1]]

        src_map: Dict[str, List[str]] = {}
        for it in hits:
            s = (it.get("filename") or it.get("source") or "Document")
            if s in top_sources:
                src_map.setdefault(s, []).append(it.get("text", ""))
        sources = top_sources
        context = "\n\n".join(f"--- {s} ---\n" + "\n\n".join(txts) for s, txts in src_map.items())
        add_to_context(q, context, sources)

        if is_about_question(q):
            # Build a concise overview for the top source
            doc_name = sources[0] if sources else ""
            prompt = get_summary_prompt(doc_name)
        elif is_definition_question(q):
            prompt = get_definition_prompt(q, sources)
        elif has_recent_context():
            prompt = get_follow_up_prompt(q, get_recent_context(), context)
        else:
            prompt = get_context_prompt(q, context, sources)

        # Intro line tailored to source type
        any_web = any((it.get("source_type") == "web") for it in hits)
        if is_about_question(q):
            yield "Here’s a quick overview based on the most relevant source: "
        else:
            if any_web:
                yield "Here’s what I found in the ingested web page(s): "
            else:
                yield "Here’s what I found in your uploaded documents: "
        # Accumulate model output and trim to sentence boundary to avoid mid-sentence cuts
        # Set target length based on intent/question type
        if is_definition_question(q):
            max_chars = 280
        elif is_about_question(q):
            max_chars = 450
        else:
            max_chars = 700

        def _clean(t: str) -> str:
            t = re.sub(r"(?im)^\s*(\*\*|__)?\s*important\s+reminder\s*:.*$", "", t)
            t = re.sub(r"(?im)^\s*(\*\*|__)?\s*sources?\s*:.*$", "", t)
            t = re.sub(r"(?im)^\s*-\s.*\.pdf.*$", "", t)
            t = re.sub(r"(?i)(for\s+educational\s+purposes\s+only|not\s+a\s+substitute\s+for\s+professional\s+medical\s+advice|consult\s+with\s+a\s+qualified\s+healthcare\s+provider)[^.]*\.?", "", t)
            t = re.sub(r"\n{3,}", "\n\n", t)
            return t.strip()

        def _smart_trim(t: str, limit: int) -> str:
            if len(t) <= limit:
                return t
            snippet = t[:limit]
            # Try to cut at last sentence end within last 160 chars of the window
            tail = snippet[-160:]
            for punct in [". ", "! ", "? "]:
                idx = tail.rfind(punct)
                if idx != -1:
                    cut = len(snippet) - len(tail) + idx + 1
                    return snippet[:cut].rstrip()
            # Fallback: cut at last newline or space
            for sep in ["\n", " "]:
                idx = snippet.rfind(sep)
                if idx != -1 and idx > limit * 0.6:
                    candidate = snippet[:idx].rstrip()
                    # Avoid endings like ':' or ',' or '('
                    while candidate and candidate[-1] in ":,(":
                        candidate = candidate[:-1].rstrip()
                    return candidate
            candidate = snippet.rstrip()
            while candidate and candidate[-1] in ":,(":
                candidate = candidate[:-1].rstrip()
            return candidate

        buffer = []
        total = 0
        for chunk in get_streaming_answer(prompt, context):
            if not chunk:
                continue
            text = _clean(chunk)
            if not text:
                continue
            if total >= max_chars:
                break
            room = max_chars - total
            take = text[: room + 200]  # soft overflow to help reach sentence boundary
            buffer.append(take)
            total += len(take)

        final_text = _smart_trim(" ".join(buffer).strip(), max_chars)
        if final_text and final_text[-1] not in ".!?":
            # If it still ends awkwardly, strip trailing ':', ',', '(' then add a period
            while final_text and final_text[-1] in ":,(":
                final_text = final_text[:-1].rstrip()
            final_text = final_text.rstrip() + "."
        if final_text:
            yield final_text + ""

        if sources:
            yield "\n\nSources: " + format_sources_with_pages(sources, {k: v for k, v in pages_by_source(hits).items() if k in sources})
    except Exception as e:
        print(f"[qa_core] unexpected: {e}\n{traceback.format_exc()}")
        yield "I'm sorry, I hit an unexpected error while answering. Please try again."
