from pathlib import Path
from dotenv import load_dotenv
import os

# Load .env from the backend directory regardless of current working directory
_ENV_PATH = Path(__file__).with_name('.env')
load_dotenv(dotenv_path=_ENV_PATH)

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
    # Optional domain switch: entertainment
    ENTERTAINMENT_API_KEY = os.getenv("ENTERTAINMENT_API_KEY", "")
    TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
    # SIMPLE_DB_URL removed: using official Qdrant client instead of custom HTTP DB
    
    @classmethod
    def init_dirs(cls):
        cls.UPLOAD_DIR.mkdir(exist_ok=True)
