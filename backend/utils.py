import os
import re
from typing import List, Dict, Any
from datetime import datetime

# Using pure AI classification - no keyword lists needed

def is_healthcare_text(text: str) -> bool:
    """AI-powered healthcare text detection using Gemini classification"""
    if not text or len(text.strip()) < 10:
        return False
    
    # Use Gemini AI for intelligent healthcare classification
    try:
        from gemini_client import check_healthcare_relevance
        result = check_healthcare_relevance(text)
        print(f"[utils] Gemini healthcare classification: {result}")
        return result
    except Exception as e:
        print(f"[utils] Gemini classification failed: {e}")
        # Fallback: assume it's healthcare if we can't classify
        return True

# Keyword-based functions removed - using pure AI classification

def load_prompt(file_path: str = "prompts.txt") -> str:
    """Load prompt from file with fallback"""
    if not os.path.exists(file_path):
        return "You are MedAssist, a helpful AI assistant specialized in healthcare. Answer only healthcare-related questions with empathy and accuracy."
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        print(f"[utils] Error loading prompt: {e}")
        return "You are MedAssist, a helpful AI assistant specialized in healthcare."

def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

def get_file_info(filepath: str) -> Dict[str, Any]:
    """Get detailed file information"""
    if not os.path.exists(filepath):
        return None
    
    stat = os.stat(filepath)
    return {
        'filename': os.path.basename(filepath),
        'size': stat.st_size,
        'size_formatted': format_file_size(stat.st_size),
        'created': datetime.fromtimestamp(stat.st_ctime),
        'modified': datetime.fromtimestamp(stat.st_mtime),
        'extension': os.path.splitext(filepath)[1].lower()
    }

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage"""
    # Remove or replace unsafe characters
    safe_chars = re.sub(r'[^\w\s.-]', '', filename)
    # Replace spaces with underscores
    safe_chars = re.sub(r'\s+', '_', safe_chars)
    # Limit length
    if len(safe_chars) > 100:
        name, ext = os.path.splitext(safe_chars)
        safe_chars = name[:95] + ext
    return safe_chars

def validate_pdf_content(text: str) -> Dict[str, Any]:
    """Validate PDF content quality and healthcare relevance"""
    validation = {
        'is_valid': True,
        'is_healthcare': False,
        'word_count': 0,
        'issues': [],
        'confidence': 0.0
    }
    
    if not text or not text.strip():
        validation['is_valid'] = False
        validation['issues'].append('No text content found')
        return validation
    
    words = text.split()
    validation['word_count'] = len(words)
    
    if len(words) < 50:
        validation['issues'].append('Document too short (less than 50 words)')
    
    # Check healthcare relevance using AI
    validation['is_healthcare'] = is_healthcare_text(text)
    
    # Set confidence based on AI classification result
    if validation['is_healthcare']:
        validation['confidence'] = 0.9  # High confidence from AI classification
    else:
        validation['confidence'] = 0.1  # Low confidence for non-healthcare
    
    return validation
