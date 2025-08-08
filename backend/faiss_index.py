# faiss_index.py

import os
import pickle
import faiss
import numpy as np
from embedding import get_embedding

FAISS_INDEX_PATH = "faiss_index/faiss.index"
CHUNKS_PATH = "faiss_index/chunks.pkl"

# Ensure necessary directories exist
os.makedirs(os.path.dirname(FAISS_INDEX_PATH), exist_ok=True)

def search_faiss_index(query: str, top_k: int = 5):
    """Search the FAISS index for similar chunks"""
    if not os.path.exists(FAISS_INDEX_PATH) or not os.path.exists(CHUNKS_PATH):
        return []
    
    try:
        # Load FAISS index
        index = faiss.read_index(FAISS_INDEX_PATH)
        
        # Load chunks
        with open(CHUNKS_PATH, "rb") as f:
            chunks = pickle.load(f)
        
        if not chunks:
            return []
        
        # Get query embedding
        query_embedding = get_embedding(query)
        
        # Search
        D, I = index.search(np.array([query_embedding]).astype("float32"), top_k)
        
        # Return top chunks
        results = []
        for idx in I[0]:
            if idx < len(chunks):
                results.append(chunks[idx])
        
        return results
    except Exception as e:
        print(f"[faiss_index] Error searching index: {e}")
        return []

def add_to_faiss_index(chunks):
    """Add chunks to FAISS index"""
    if not chunks:
        return
    
    try:
        # Get embeddings
        embeddings = [chunk['embedding'] for chunk in chunks]
        
        # Create or load index
        if os.path.exists(FAISS_INDEX_PATH):
            index = faiss.read_index(FAISS_INDEX_PATH)
        else:
            dim = len(embeddings[0])
            index = faiss.IndexFlatL2(dim)
        
        # Add to index
        index.add(np.array(embeddings).astype("float32"))
        
        # Save index
        faiss.write_index(index, FAISS_INDEX_PATH)
        
        # Save chunks
        with open(CHUNKS_PATH, "wb") as f:
            pickle.dump(chunks, f)
            
        print(f"[faiss_index] Added {len(chunks)} chunks to index")
    except Exception as e:
        print(f"[faiss_index] Error adding to index: {e}")
