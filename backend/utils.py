import os
import re
from datetime import datetime
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

def is_healthcare_text(text: str) -> bool:
    """Check if text is healthcare-related using Gemini AI or default to True."""
    if not text or len(text.strip()) < 10:
        return False
    try:
        from gemini_client import check_healthcare_relevance
        return bool(check_healthcare_relevance(text))
    except (ImportError, Exception) as e:
        print(f"[utils] Healthcare check: {getattr(e, '__class__.__name__', type(e).__name__)}")
        return True

def load_prompt(file_path: str = "prompts.txt") -> str:
    """Load prompt from file or return default if not found."""
    default = (
        "You are a helpful, concise, and human-like document assistant. "
        "Answer clearly using only the provided content."
    )
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read().strip() or default
    except Exception:
        return default

def format_file_size(size_bytes: int) -> str:
    """Convert bytes to human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f}TB"

def get_file_info(filepath: str) -> Optional[Dict[str, Any]]:
    """Get file metadata or None if not found."""
    try:
        stat = os.stat(filepath)
        return {
            'filename': os.path.basename(filepath),
            'size': stat.st_size,
            'created': datetime.fromtimestamp(stat.st_ctime),
            'modified': datetime.fromtimestamp(stat.st_mtime),
            'is_file': os.path.isfile(filepath),
            'is_dir': os.path.isdir(filepath)
        }
    except (OSError, AttributeError):
        return None

def sanitize_filename(filename: str) -> str:
    """Make filename safe for storage."""
    return re.sub(r'\s+', '_', re.sub(r'[^\w\s.-]', '', filename)).strip(' .')

def validate_pdf_content(text: str) -> Dict[str, Any]:
    """Basic PDF text validation (domain-agnostic)."""
    if not text or len(text.strip()) < 100:
        return {'valid': False, 'reason': 'Empty or too short'}
    return {'valid': True, 'reason': 'OK'}
