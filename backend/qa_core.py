
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
from qa_utils import extract_name_phrase, clean_model_chunk, smart_trim, tidy_text
from entertainment import get_entertainment_answer


def answer_question_stream(question: str, entertainment_enabled: bool = False) -> Generator[str, None, None]:
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
            ql = (q or "").lower().strip()
            # Only treat as smalltalk if it's a standalone greeting/ack message.
            # If there's a question mark or extra content after the smalltalk token, do NOT intercept.
            if ("?" in ql) or re.search(r"\b(ok|okay|thanks|thank you)\b.+", ql):
                pass  # fall through to normal answering
            elif re.fullmatch(r"(thank you|thanks)[.! ]*", ql):
                yield "You're welcome! If you have more questions about your documents or web sources, just ask. 😊"; return
            elif re.fullmatch(r"(ok|okay)[.! ]*", ql):
                yield "Got it. When you're ready, ask me about your uploaded PDFs or ingested web pages!"; return
            elif re.fullmatch(r"(hi|hello|hey)[.! ]*", ql):
                yield "I'm here and happy to help! Ask about your uploaded PDFs or ingested web pages. 😊"; return

        # Entertainment mode: bypass retrieval and answer directly with the LLM (previous behavior)
        if entertainment_enabled:
            # First try hybrid factual answer (TMDb roles + OMDb details)
            hybrid = None
            try:
                hybrid = get_entertainment_answer(q)
            except Exception:
                hybrid = None
            if hybrid:
                # Store context for follow-ups and return
                hints = get_recent_context() if has_recent_context() else ""
                try:
                    add_to_context(q, hints, [])
                except Exception:
                    pass
                yield tidy_text(smart_trim(hybrid.strip(), 2000))
                return

            # Fallback: LLM entertainment prompt with conversation hints
            hints = get_recent_context() if has_recent_context() else ""
            ent_prefix = (
                "You are in Entertainment mode. Act as a movies/TV Q&A assistant. "
                "Answer directly, clearly, and humanly without restricting to medical topics."
            )
            if hints:
                prompt = f"{ent_prefix}\n\nConversation hints (for reference only):\n{hints}\n\nUser: {q}"
            else:
                prompt = f"{ent_prefix}\n\nUser: {q}"
            accum = ""; total = 0; max_chars = 2000
            for chunk in get_streaming_answer(prompt, context=""):
                if not chunk: continue
                text = clean_model_chunk(chunk)
                if not text: continue
                if total >= max_chars: break
                room = max_chars - total
                take = text[: room + 200]
                if accum:
                    prev = accum[-1]; first = take[0]
                    if prev.isalnum() and first.isalnum():
                        prev_token = re.findall(r"([A-Za-z0-9]+)$", accum[-10:])
                        prev_tok = prev_token[0] if prev_token else ""
                        if not (len(prev_tok) == 1 and first.islower()):
                            accum += " "
                accum += take; total += len(take)
            final_text = tidy_text(smart_trim(accum.strip(), max_chars))
            if final_text and final_text[-1] not in ".!?":
                while final_text and final_text[-1] in ":,(":
                    final_text = final_text[:-1].rstrip()
                final_text = final_text.rstrip() + "."
            if final_text:
                # Save turn to conversation context for future follow-ups
                try:
                    add_to_context(q, hints, [])
                except Exception:
                    pass
                yield final_text
            else:
                yield "I couldn't generate a response just now. Please try again, or rephrase your question."
            return

        # No domain gating (healthcare/doc mode): answer from uploaded PDFs and ingested web pages.

        emb = get_embedding(q)
        # Retrieve from both docs and web, then COMBINE results so we consider all uploaded items
        doc_hits = search_similar_chunks(emb, k=20)
        web_hits = search_web_chunks(emb, k=20)

        def _contains_any_tokens(items, tokens):
            if not items or not tokens:
                return 0
            count = 0
            for it in items:
                txt = (it.get("text") or "").lower()
                if any(t in txt for t in tokens):
                    count += 1
            return count

        # Token cues from query
        qtoks = [t for t in re.split(r"[^a-z0-9]+", (q or "").lower()) if len(t) >= 4]
        ql = (q or "").lower()
        prefer_web_by_phrase = any(p in ql for p in [
            "website", "web site", "webpage", "link", "url", "according to the link", "on the site", "from the site"
        ])
        mentions_docs = any(p in ql for p in ["document", "documents", "pdf", "pdfs", "uploaded files", "files"])

        # Detect multi-part questions EARLY so source selection can respect it
        try:
            ql_check = ql
            multi_part = bool(re.search(r"\b(who|what|which|where|when|how)\b.*[,;]|\bwho\s+is\b.*\bwhat\s+|\bwhat\s+is\b.*\band\b", ql_check))
        except Exception:
            multi_part = False

        # Combine and sort by score so the model sees best evidence from ALL sources
        combined = (doc_hits or []) + (web_hits or [])
        hits = sorted(combined, key=lambda x: float(x.get("score", 0.0)), reverse=True)

        # If the user explicitly asks about the URL/site/link, prioritize web chunks.
        # For multi-part questions, do NOT force web-only; keep both docs and web for coverage.
        if prefer_web_by_phrase and not mentions_docs and not multi_part:
            web_only = []
            for it in hits:
                src = (it.get("source") or it.get("filename") or "")
                # Prefer items that clearly look like URLs (from web store)
                if isinstance(src, str) and (src.startswith("http") or "http" in src):
                    web_only.append(it)
                else:
                    # Some stores put metadata in payload
                    md = it.get("metadata") or {}
                    url_val = (md.get("url") or md.get("page_url") or md.get("source_url") or "")
                    if (md.get("source_type") or "").lower() == "web" or (isinstance(url_val, str) and url_val.startswith("http")):
                        web_only.append(it)
            if web_only:
                hits = web_only
        if not hits:
            yield "I couldn't find relevant information in the uploaded documents. Please try rephrasing."; return

        # Lightweight re-ranking: names handling
        name_phrase = extract_name_phrase(q)
        if name_phrase:
            # If only a common surname is provided, ask for the full name to avoid ambiguity
            surname_only = [t for t in re.split(r"[^a-z0-9]+", name_phrase.lower()) if t]
            common_surnames = {"reddy", "kumar", "singh", "patel", "gupta", "rao"}
            if len(surname_only) == 1 and surname_only[0] in common_surnames:
                yield "Please provide the full name (first and last) to avoid confusion among multiple people sharing that surname."; return
            np = name_phrase
            boosted = []
            for it in hits:
                txt = (it.get("text") or "").lower()
                sc = float(it.get("score", 0.0))
                bump = 0.0
                if np and np in txt:
                    bump += 0.25  # significant boost for exact phrase
                else:
                    # Token overlap boost (helpful for slight OCR/name variations)
                    q_toks = [t for t in re.split(r"[^a-z0-9]+", np) if len(t) > 2]
                    if q_toks and all(t in txt for t in q_toks):
                        bump += 0.15
                    # Proximity boost: if first and last tokens appear within a small window in order
                    if len(q_toks) >= 2:
                        first, last = q_toks[0], q_toks[-1]
                        tokens = [t for t in re.split(r"[^a-z0-9]+", txt) if t]
                        try:
                            fi = tokens.index(first)
                            li = tokens.index(last, fi)
                            if 0 <= fi < li and (li - fi) <= 5:
                                bump += 0.20
                        except ValueError:
                            pass
                if bump:
                    it["score"] = sc + bump
                boosted.append(it)
            # Re-sort with adjusted scores
            hits = sorted(boosted, key=lambda x: float(x.get("score", 0.0)), reverse=True)

            # Strict filter: if any chunks contain all name tokens, keep only those
            name_tokens = [t for t in re.split(r"[^a-z0-9]+", np) if len(t) > 2]
            if name_tokens:
                filtered = [it for it in hits if all(t in (it.get("text") or "").lower() for t in name_tokens)]
                if filtered:
                    hits = filtered
                else:
                    # Fallback: keep only chunks with the maximum count of overlapping tokens (>=1)
                    scored = []
                    for it in hits:
                        txt = (it.get("text") or "").lower()
                        cnt = sum(1 for t in name_tokens if t in txt)
                        scored.append((cnt, it))
                    max_cnt = max((c for c, _ in scored), default=0)
                    if max_cnt > 0:
                        hits = [it for c, it in scored if c == max_cnt]

        # Build context using ONLY a few top sources by aggregate score, ensuring diversity across doc and web when available
        score_by_source: Dict[str, float] = {}
        kind_by_source: Dict[str, str] = {}  # 'web' | 'doc'
        for it in hits:
            s = it.get("filename") or it.get("source") or "Document"
            score_by_source[s] = score_by_source.get(s, 0.0) + float(it.get("score", 0.0))
            if s not in kind_by_source:
                md = it.get("metadata") or {}
                src = (it.get("source") or "")
                is_web = (md.get("source_type", "").lower() == "web") or (isinstance(src, str) and (src.startswith("http") or "http" in src))
                kind_by_source[s] = "web" if is_web else "doc"
        # Target number of sources
        top_n = 1 if name_phrase else 3
        # Pick the top web and top doc when available, then fill remaining by score
        web_sources = [s for s in score_by_source if kind_by_source.get(s) == "web"]
        doc_sources = [s for s in score_by_source if kind_by_source.get(s) == "doc"]
        top_web = max(web_sources, key=lambda s: score_by_source[s]) if web_sources else None
        top_doc = max(doc_sources, key=lambda s: score_by_source[s]) if doc_sources else None
        selected = []
        if top_doc: selected.append(top_doc)
        if top_web and top_web not in selected: selected.append(top_web)
        # Fill remaining slots by global score order
        remaining = [s for s, _ in sorted(score_by_source.items(), key=lambda x: x[1], reverse=True) if s not in selected]
        for s in remaining:
            if len(selected) >= top_n: break
            selected.append(s)
        top_sources = selected[:top_n]

        src_map: Dict[str, List[str]] = {}
        for it in hits:
            s = (it.get("filename") or it.get("source") or "Document")
            if s in top_sources:
                src_map.setdefault(s, []).append(it.get("text", ""))
        sources = top_sources
        context = "\n\n".join(f"--- {s} ---\n" + "\n\n".join(txts) for s, txts in src_map.items())
        add_to_context(q, context, sources)

        # multi_part already computed earlier

        if is_about_question(q):
            # Build a concise overview for the top source
            doc_name = sources[0] if sources else ""
            prompt = get_summary_prompt(doc_name)
        elif is_definition_question(q) and not multi_part:
            prompt = get_definition_prompt(q, sources)
        elif has_recent_context():
            prompt = get_follow_up_prompt(q, get_recent_context(), context)
        else:
            prompt = get_context_prompt(q, context, sources)

        # Do not emit any intro line; start directly with the answer content for cleaner formatting
        # Accumulate model output and trim to sentence boundary to avoid mid-sentence cuts
        # Set target length based on intent/question type (slightly larger to avoid mid-list truncation)
        if is_definition_question(q) and not multi_part:
            max_chars = 380
        elif is_about_question(q):
            max_chars = 700
        else:
            max_chars = 1800

        # Use shared helpers for cleaning and trimming

        # Boundary-aware accumulation to avoid both missing spaces ("isan") and mid-word spaces ("P neumonia")
        accum = ""
        total = 0
        for chunk in get_streaming_answer(prompt, context):
            if not chunk:
                continue
            text = clean_model_chunk(chunk)
            if not text:
                continue
            if total >= max_chars:
                break
            room = max_chars - total
            take = text[: room + 200]  # soft overflow to help reach sentence boundary

            if accum:
                prev = accum[-1]
                first = take[0]
                # Decide if a space is needed at the boundary
                if prev.isalnum() and first.isalnum():
                    # Check if previous token is a single letter (likely a split word like "P" + "neumonia")
                    prev_token = re.findall(r"([A-Za-z0-9]+)$", accum[-10:])
                    prev_tok = prev_token[0] if prev_token else ""
                    if not (len(prev_tok) == 1 and first.islower()):
                        accum += " "
            accum += take
            total += len(take)

        final_text = smart_trim(accum.strip(), max_chars)
        final_text = tidy_text(final_text)
        if final_text and final_text[-1] not in ".!?":
            # If it still ends awkwardly, strip trailing ':', ',', '(' then add a period
            while final_text and final_text[-1] in ":,(":
                final_text = final_text[:-1].rstrip()
            final_text = final_text.rstrip() + "."
        if final_text:
            src_block = ""
            if sources:
                src_block = "\n\nSources:\n" + format_sources_with_pages(sources, {k: v for k, v in pages_by_source(hits).items() if k in sources})
            # Yield answer and sources together so clients that read only the first chunk still show sources
            yield final_text + src_block
    except Exception as e:
        print(f"[qa_core] unexpected: {e}\n{traceback.format_exc()}")
        yield "I'm sorry, I hit an unexpected error while answering. Please try again."
