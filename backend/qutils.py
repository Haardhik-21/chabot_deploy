"""Qdrant-related small utilities to keep other modules short."""
from typing import Dict, List, Any
import os


def pages_by_source(hits: List[Dict[str, Any]]) -> Dict[str, set]:
    out: Dict[str, set] = {}
    for it in hits or []:
        src = it.get("filename") or it.get("source") or "Document"
        pg = it.get("page")
        if pg is None:
            continue
        out.setdefault(src, set()).add(str(pg))
    return out


def format_sources_with_pages(sources: List[str], pmap: Dict[str, set]) -> str:
    def fmt(s: str) -> str:
        base = os.path.basename(s)
        pgs = sorted(pmap.get(s, pmap.get(base, set())))
        return f"{base} (p. {', '.join(pgs)})" if pgs else base
    return ", ".join(fmt(s) for s in sources)
