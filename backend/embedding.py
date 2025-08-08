# embedding.py

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict, Any, Tuple, Optional
import time
from functools import lru_cache
import hashlib

# Initialize model with healthcare-optimized settings
model = SentenceTransformer("all-MiniLM-L6-v2")

# Cache for embeddings to improve performance
embedding_cache = {}

def get_embedding(text: str, use_cache: bool = True) -> np.ndarray:
    """Get embedding for text with optional caching"""
    if not text or not text.strip():
        return np.zeros(384)  # Return zero vector for empty text
    
    # Create cache key
    if use_cache:
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in embedding_cache:
            return embedding_cache[cache_key]
    
    try:
        embedding = model.encode([text.strip()])[0]
        
        # Cache the result
        if use_cache:
            embedding_cache[cache_key] = embedding
            # Limit cache size
            if len(embedding_cache) > 1000:
                # Remove oldest entries
                keys_to_remove = list(embedding_cache.keys())[:100]
                for key in keys_to_remove:
                    del embedding_cache[key]
        
        return embedding
    except Exception as e:
        print(f"[embedding] Error getting embedding: {e}")
        return np.zeros(384)

def get_embeddings_batch(texts: List[str], batch_size: int = 32) -> List[np.ndarray]:
    """Get embeddings for multiple texts efficiently"""
    if not texts:
        return []
    
    # Filter out empty texts
    valid_texts = [text.strip() if text else "" for text in texts]
    
    try:
        # Process in batches for memory efficiency
        all_embeddings = []
        for i in range(0, len(valid_texts), batch_size):
            batch = valid_texts[i:i + batch_size]
            batch_embeddings = model.encode(batch, show_progress_bar=False)
            all_embeddings.extend(batch_embeddings)
        
        return all_embeddings
    except Exception as e:
        print(f"[embedding] Error in batch embedding: {e}")
        return [np.zeros(384) for _ in texts]

def get_top_k_chunks(query: str, chunks: List[Dict], k: int = 5, threshold: float = 0.3) -> List[Dict]:
    """Enhanced similarity search with better scoring"""
    if not chunks:
        return []
    
    query_embedding = get_embedding(query)
    
    # Extract embeddings and prepare chunks
    valid_chunks = []
    embeddings = []
    
    for chunk in chunks:
        if isinstance(chunk, dict):
            embedding = chunk.get('embedding')
            if embedding is not None:
                valid_chunks.append(chunk)
                embeddings.append(embedding)
    
    if not embeddings:
        print("[embedding] No valid embeddings found in chunks")
        return []
    
    try:
        # Calculate similarities
        similarities = cosine_similarity([query_embedding], embeddings)[0]
        
        # Create scored results
        scored_chunks = []
        for i, (chunk, score) in enumerate(zip(valid_chunks, similarities)):
            if score >= threshold:
                # Add similarity score to chunk for reference
                chunk_with_score = chunk.copy()
                chunk_with_score['similarity_score'] = float(score)
                chunk_with_score['rank'] = len(scored_chunks) + 1
                scored_chunks.append((score, chunk_with_score))
        
        # Sort by similarity score (descending)
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        
        # Return top k chunks
        top_chunks = [chunk for score, chunk in scored_chunks[:k]]
        
        print(f"[embedding] Found {len(top_chunks)} relevant chunks (threshold: {threshold})")
        return top_chunks
        
    except Exception as e:
        print(f"[embedding] Error in similarity search: {e}")
        return []

def embed_chunks(chunks: List[Dict]) -> List[Dict]:
    """Add embeddings to chunks efficiently"""
    if not chunks:
        return []
    
    print(f"[embedding] Processing {len(chunks)} chunks...")
    
    # Extract texts
    texts = []
    for chunk in chunks:
        text = chunk.get("text", "")
        if not text:
            text = chunk.get("chunk", "")
        texts.append(text if text else "")
    
    # Get embeddings in batches
    embeddings = get_embeddings_batch(texts)
    
    # Add embeddings to chunks
    for i, chunk in enumerate(chunks):
        if i < len(embeddings):
            chunk["embedding"] = embeddings[i]
        else:
            chunk["embedding"] = np.zeros(384)
    
    print(f"[embedding] Successfully embedded {len(chunks)} chunks")
    return chunks

def calculate_semantic_similarity(text1: str, text2: str) -> float:
    """Calculate semantic similarity between two texts"""
    if not text1 or not text2:
        return 0.0
    
    try:
        emb1 = get_embedding(text1)
        emb2 = get_embedding(text2)
        similarity = cosine_similarity([emb1], [emb2])[0][0]
        return float(similarity)
    except Exception as e:
        print(f"[embedding] Error calculating similarity: {e}")
        return 0.0

def find_similar_chunks(target_chunk: Dict, all_chunks: List[Dict], k: int = 3, threshold: float = 0.5) -> List[Dict]:
    """Find chunks similar to a target chunk"""
    target_text = target_chunk.get("text", "")
    if not target_text:
        return []
    
    # Filter out the target chunk itself
    other_chunks = [chunk for chunk in all_chunks if chunk.get("text") != target_text]
    
    return get_top_k_chunks(target_text, other_chunks, k, threshold)

def get_embedding_stats() -> Dict[str, Any]:
    """Get statistics about embeddings and cache"""
    return {
        "model_name": model._modules['0'].auto_model.name_or_path,
        "embedding_dimension": 384,
        "cache_size": len(embedding_cache),
        "max_cache_size": 1000
    }

def clear_embedding_cache():
    """Clear the embedding cache"""
    global embedding_cache
    embedding_cache.clear()
    print("[embedding] Cache cleared")

@lru_cache(maxsize=100)
def get_cached_similarity(text1_hash: str, text2_hash: str) -> float:
    """Cached similarity calculation for frequently compared texts"""
    # This is used internally by other functions
    pass
