"""Compact Qdrant vector store core (<200 lines)."""
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, PointIdsList
from config import Config
import time
import logging

_client = QdrantClient(url=Config.QDRANT_URL, api_key=Config.QDRANT_API_KEY or None, timeout=30)
_COLLECTION = Config.QDRANT_COLLECTION
_VECTOR_SIZE = 384

def _ensure_collection() -> bool:
    try:
        cols = {c.name for c in _client.get_collections().collections}
        if _COLLECTION not in cols:
            _client.create_collection(_COLLECTION, vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE))
        else:
            info = _client.get_collection(_COLLECTION)
            if getattr(info.config.params.vectors, "size", _VECTOR_SIZE) != _VECTOR_SIZE:
                _client.delete_collection(_COLLECTION)
                _client.create_collection(_COLLECTION, vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE))
        return True
    except Exception as e:
        print(f"[vector_core] _ensure_collection error: {e}")
        return False

def _ensure_collection_for(name: str) -> bool:
    try:
        cols = {c.name for c in _client.get_collections().collections}
        if name not in cols:
            _client.create_collection(name, vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE))
        else:
            info = _client.get_collection(name)
            if getattr(info.config.params.vectors, "size", _VECTOR_SIZE) != _VECTOR_SIZE:
                _client.delete_collection(name)
                _client.create_collection(name, vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE))
        return True
    except Exception as e:
        logging.error(f"[vector_core] _ensure_collection_for('{name}') error: {e}")
        return False

def _points_from_chunks(chunks: List[Dict]) -> List[PointStruct]:
    pts: List[PointStruct] = []
    ts = int(time.time() * 1000)
    for i, c in enumerate(chunks):
        emb = c.get("embedding")
        if not emb:
            continue
        pid = abs(hash(c.get("id", f"{ts}_{i}"))) % (10 ** 12)
        # Preserve original 'source' (full path or URL) if present; use 'filename' only for the basename
        original_source = c.get("source") or c.get("file") or c.get("filename") or "unknown"
        filename = c.get("filename") or original_source
        payload = {
            "text": c.get("text") or c.get("chunk", ""),
            "filename": filename,
            "source": original_source,
            "chunk_number": c.get("chunk_number") or c.get("page"),
        }
        meta = c.get("metadata") or {}
        if isinstance(meta, dict):
            payload.update(meta)
        pts.append(PointStruct(id=pid, vector=list(emb), payload=payload))
    return pts

def save_chunks_to_store(chunks: List[Dict]) -> bool:
    if not chunks or not _ensure_collection(): return False
    pts = _points_from_chunks(chunks)
    if not pts: return False
    try: _client.upsert(collection_name=_COLLECTION, points=pts, wait=True); return True
    except Exception: return False

def save_chunks_to_web_store(chunks: List[Dict]) -> bool:
    if not chunks: return False
    name = getattr(Config, "QDRANT_WEB_COLLECTION", "healthcare_web")
    if not _ensure_collection_for(name): return False
    pts = _points_from_chunks([{**c, "metadata": {**(c.get("metadata") or {}), "source_type": "web"}} for c in chunks])
    if not pts: return False
    try: _client.upsert(collection_name=name, points=pts, wait=True); return True
    except Exception: return False

def search_similar_chunks(query_embedding: List[float], k: int = 5, **filters) -> List[Dict[str, Any]]:
    if not _ensure_collection(): return []
    must = [FieldCondition(key=k, match=MatchValue(value=v)) for k, v in filters.items() if v is not None]
    qf: Optional[Filter] = Filter(must=must) if must else None
    rs = _client.search(collection_name=_COLLECTION, query_vector=list(query_embedding), limit=k, query_filter=qf, with_payload=True, with_vectors=False)
    out: List[Dict[str, Any]] = []
    for r in rs:
        p = r.payload or {}; p["score"] = float(getattr(r, "score", 0.0)); out.append(p)
    return out

def has_web_content() -> bool:
    name = getattr(Config, "QDRANT_WEB_COLLECTION", "healthcare_web")
    if not _ensure_collection_for(name): return False
    try:
        pts, _ = _client.scroll(collection_name=name, with_payload=False, with_vectors=False, limit=1)
        return bool(pts)
    except Exception as e:
        print(f"[vector_core] delete_web_source unexpected error: {e}")
        # Treat as success to keep DELETE idempotent and avoid surfacing 500s to the client
        return True

def search_web_chunks(query_embedding: List[float], k: int = 5) -> List[Dict[str, Any]]:
    name = getattr(Config, "QDRANT_WEB_COLLECTION", "healthcare_web")
    if not _ensure_collection_for(name): return []
    rs = _client.search(collection_name=name, query_vector=list(query_embedding), limit=k, with_payload=True, with_vectors=False)
    out: List[Dict[str, Any]] = []
    for r in rs:
        p = r.payload or {}; p["score"] = float(getattr(r, "score", 0.0)); out.append(p)
    return out

def list_web_sources(limit: int = 1000) -> Dict[str, Any]:
    name = getattr(Config, "QDRANT_WEB_COLLECTION", "healthcare_web")
    if not _ensure_collection_for(name): return {"total_urls": 0, "total_chunks": 0, "sources": []}
    uniq: Dict[str, int] = {}; token = None; total = 0
    while True:
        recs, token = _client.scroll(collection_name=name, with_payload=True, with_vectors=False, limit=min(256, max(1, limit - total)), offset=token)
        if not recs: break
        for r in recs:
            src = (r.payload or {}).get("source") or (r.payload or {}).get("filename");
            if not src: continue
            uniq[src] = uniq.get(src, 0) + 1; total += 1
            if total >= limit: token = None; break
        if not token or total >= limit: break
    sources = [{"url": k, "chunks": v} for k, v in sorted(uniq.items(), key=lambda x: x[0])]
    return {"total_urls": len(sources), "total_chunks": sum(uniq.values()), "sources": sources}

def delete_web_source(url: str) -> bool:
    name = getattr(Config, "QDRANT_WEB_COLLECTION", "healthcare_web")
    if not url or not _ensure_collection_for(name):
        return False
    try:
        # Normalization helpers
        def norm(u: str) -> str:
            try:
                p = urlparse(u.strip())
                host = (p.netloc or u).lower()
                path = (p.path or "/").rstrip("/") or "/"
                return host + path
            except Exception:
                return u.strip().lower().rstrip("/")

        def strip_qf(u: str) -> str:
            try:
                p = urlparse(u.strip())
                return (p.scheme + "://" if p.scheme else "") + (p.netloc or "").lower() + (p.path or "/")
            except Exception:
                return u

        # Build variants including without query/fragment, with/without scheme, with/without trailing slash
        base = strip_qf(url)
        n = norm(url)
        host_path = n
        host_path_slash = n if n.endswith("/") else n + "/"
        full_http = ("http://" + host_path)
        full_https = ("https://" + host_path)
        full_http_slash = ("http://" + host_path_slash)
        full_https_slash = ("https://" + host_path_slash)
        candidates = [
            url,
            base,
            host_path,
            host_path_slash,
            full_http,
            full_https,
            full_http_slash,
            full_https_slash,
        ]

        # Delete by filter across both 'source' and 'filename'
        should_conds = []
        for v in candidates:
            should_conds.append(FieldCondition(key="source", match=MatchValue(value=v)))
            should_conds.append(FieldCondition(key="filename", match=MatchValue(value=v)))
        if should_conds:
            try:
                _client.delete(collection_name=name, filter=Filter(should=should_conds), wait=True)
            except Exception as e:
                # Log but continue with ID-based fallback
                print(f"[vector_core] filter delete failed, will fallback to scan: {e}")

        # Fallback: scan and delete by exact normalized match on either field
        recs, token = _client.scroll(collection_name=name, with_payload=["source", "filename"], with_vectors=False, limit=256)
        target = norm(url)
        ids_to_delete = []
        while recs:
            for r in recs:
                pld = r.payload or {}
                s = str(pld.get("source") or "")
                f = str(pld.get("filename") or "")
                if norm(s) == target or norm(f) == target:
                    ids_to_delete.append(r.id)
            if not token:
                break
            recs, token = _client.scroll(collection_name=name, with_payload=["source", "filename"], with_vectors=False, limit=256, offset=token)
        if ids_to_delete:
            try:
                _client.delete(collection_name=name, points_selector=PointIdsList(points=ids_to_delete), wait=True)
            except Exception as e:
                print(f"[vector_core] id delete failed after scan: {e}")

        # Even if nothing matched, treat as success (idempotent delete)
        return True
    except Exception:
        return False

def delete_chunks_for_file(filename: str) -> bool:
    if not _ensure_collection(): return False
    try:
        full = str(Config.UPLOAD_DIR / filename)
        _client.delete(collection_name=_COLLECTION, filter=Filter(should=[
            FieldCondition(key="filename", match=MatchValue(value=filename)),
            FieldCondition(key="source", match=MatchValue(value=filename)),
            FieldCondition(key="source_file", match=MatchValue(value=filename)),
            FieldCondition(key="source", match=MatchValue(value=full)),
        ]), wait=True)
        return True
    except Exception:
        return False

def clear_all_chunks() -> bool:
    try:
        _client.delete_collection(_COLLECTION)
        _client.create_collection(_COLLECTION, vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE))
        return True
    except Exception:
        return False

def load_all_uploaded_chunks(limit: int = 2000) -> List[Dict[str, Any]]:
    if not _ensure_collection(): return []
    try:
        recs, _ = _client.scroll(collection_name=_COLLECTION, with_payload=True, limit=min(limit, 2000))
        return [{"id": str(r.id), "payload": r.payload or {}} for r in recs]
    except Exception:
        return []

