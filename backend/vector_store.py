import os
import pickle
import faiss
import numpy as np

FAISS_INDEX_PATH = "faiss_index/faiss.index"
CHUNKS_PATH = "faiss_index/chunks.pkl"
os.makedirs("faiss_index", exist_ok=True)

def save_chunks_to_store(chunks, filename=None):
    with open(CHUNKS_PATH, "wb") as f:
        pickle.dump(chunks, f)
    print(f"[vector_store] Saved {len(chunks)} chunks")

def load_all_uploaded_chunks():
    if not os.path.exists(CHUNKS_PATH):
        return []
    with open(CHUNKS_PATH, "rb") as f:
        return pickle.load(f)

def clear_all_chunks():
    if os.path.exists(CHUNKS_PATH):
        os.remove(CHUNKS_PATH)
    if os.path.exists(FAISS_INDEX_PATH):
        os.remove(FAISS_INDEX_PATH)
    print("[vector_store] Cleared all stored chunks and FAISS index.")

def delete_chunks_for_file(filename: str):
    if not os.path.exists(CHUNKS_PATH):
        return
    with open(CHUNKS_PATH, "rb") as f:
        chunks = pickle.load(f)
    chunks = [c for c in chunks if c.get("source") != filename]
    save_chunks_to_store(chunks)
    rebuild_faiss_index(chunks)

def get_uploaded_files():
    chunks = load_all_uploaded_chunks()
    return list({chunk.get("source", "unknown") for chunk in chunks})

def store_embeddings(chunks):
    """Store embeddings by appending to existing index for multiple PDFs"""
    if not chunks:
        return
    
    # Load existing chunks
    existing_chunks = load_all_uploaded_chunks()
    
    # Combine with new chunks
    all_chunks = existing_chunks + chunks
    
    # Rebuild the entire index with all chunks
    rebuild_faiss_index(all_chunks)
    
    print(f"[vector_store] Added {len(chunks)} new chunks. Total: {len(all_chunks)} chunks in FAISS.")

def rebuild_faiss_index(chunks):
    if not chunks:
        clear_all_chunks()
        return
    dim = len(chunks[0]["embedding"])
    index = faiss.IndexFlatL2(dim)
    embeddings = [chunk["embedding"] for chunk in chunks]
    index.add(np.array(embeddings).astype("float32"))
    faiss.write_index(index, FAISS_INDEX_PATH)
    save_chunks_to_store(chunks)

def search_similar_chunks(query_embedding, k=5, threshold=None):
    """Search for similar chunks with optional similarity threshold"""
    if not os.path.exists(FAISS_INDEX_PATH) or not os.path.exists(CHUNKS_PATH):
        return []
    
    index = faiss.read_index(FAISS_INDEX_PATH)
    with open(CHUNKS_PATH, "rb") as f:
        chunks = pickle.load(f)
    
    # Search with potentially larger k for threshold filtering
    search_k = min(k * 2, len(chunks)) if threshold else k
    D, I = index.search(np.array([query_embedding]).astype("float32"), search_k)
    
    results = []
    for i, distance in zip(I[0], D[0]):
        if 0 <= i < len(chunks):
            chunk = chunks[i]
            
            # Apply threshold if specified (convert L2 distance to similarity)
            if threshold is not None:
                # Convert L2 distance to cosine similarity approximation
                similarity = 1 / (1 + distance)
                if similarity < threshold:
                    continue
                chunk['similarity_score'] = similarity
            
            results.append(chunk)
            
            # Stop if we have enough results
            if len(results) >= k:
                break
    
    return results
