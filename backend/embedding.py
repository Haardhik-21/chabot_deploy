import hashlib
from typing import List, Dict, Any
import numpy as np

try:
    from sentence_transformers import SentenceTransformer
except Exception as _e:
    SentenceTransformer = None  # type: ignore

# Embedding configuration
EMBED_DIM = 384
BATCH_SIZE = 32

# Lazy model holder
_model = None

def _get_model():
    global _model
    if _model is None:
        if SentenceTransformer is None:
            raise RuntimeError("sentence-transformers not available")
        # Try primary model name, then HF hub path fallback
        try:
            _model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception:
            _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _model

# Simple LRU-like cache
_embed_cache: Dict[str, List[float]] = {}

def get_embedding(text: str, use_cache: bool = True) -> List[float]:
    """Get an embedding with simple caching. Always returns list[float]."""
    if not (text or '').strip():
        return [0.0] * EMBED_DIM

    key = hashlib.md5(text.encode()).hexdigest()
    if use_cache and key in _embed_cache:
        return _embed_cache[key]

    try:
        model = _get_model()
        vec = model.encode([text.strip()], show_progress_bar=False)[0]
        # Ensure list[float]
        embedding = vec.tolist() if hasattr(vec, 'tolist') else list(vec)
        if use_cache:
            _embed_cache[key] = embedding
            if len(_embed_cache) > 1000:
                _embed_cache.clear()
        return embedding
    except Exception as e:
        print(f"[embed] Error: {e}")
        return [0.0] * EMBED_DIM

def get_embeddings_batch(texts: List[str], batch_size: int = BATCH_SIZE) -> List[List[float]]:
    """Batch encode texts into embeddings. Returns list of list[float]."""
    if not texts:
        return []
    try:
        model = _get_model()
        out: List[List[float]] = []
        for i in range(0, len(texts), batch_size):
            chunk = [t.strip() for t in texts[i:i + batch_size] if t]
            if not chunk:
                continue
            vecs = model.encode(chunk, show_progress_bar=False)
            for v in vecs:
                out.append(v.tolist() if hasattr(v, 'tolist') else list(v))
        return out
    except Exception as e:
        print(f"[embed] Batch error: {e}")
        return [[0.0] * EMBED_DIM for _ in texts]

def embed_chunks(chunks: List[Dict]) -> List[Dict]:
    """Attach embeddings to chunks in-place and return them."""
    if not chunks:
        return []

    texts = [c.get("text") or c.get("chunk", "") for c in chunks]
    for chunk, emb in zip(chunks, get_embeddings_batch(texts)):
        chunk["embedding"] = emb
    return chunks
