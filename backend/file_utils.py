from pathlib import Path
from typing import List, Dict, Any
from fastapi import UploadFile
import shutil

def save_uploaded_file(file: UploadFile, upload_dir: Path) -> Path:
    """Save uploaded file and return its path."""
    filepath = upload_dir / file.filename
    with filepath.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return filepath

def cleanup_file(filepath: Path):
    """Remove file if it exists."""
    if filepath.exists():
        filepath.unlink()

def clear_directory(directory: Path):
    """Remove all files in directory."""
    for file in directory.glob("*"):
        if file.is_file():
            file.unlink()
