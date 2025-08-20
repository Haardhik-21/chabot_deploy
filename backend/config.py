from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

class Config:
    UPLOAD_DIR = Path("uploaded_files")
    MAX_FILES = 3
    CHUNK_SIZE = 1000
    CHUNK_OVERLAP = 200
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
    QDRANT_COLLECTION = "healthcare_docs"
    # Separate collection for web-scraped content (Option A)
    QDRANT_WEB_COLLECTION = os.getenv("QDRANT_WEB_COLLECTION", "healthcare_web")
    # SIMPLE_DB_URL removed: using official Qdrant client instead of custom HTTP DB
    
    @classmethod
    def init_dirs(cls):
        cls.UPLOAD_DIR.mkdir(exist_ok=True)
