from pathlib import Path
from typing import List, Dict, Any
from fastapi import UploadFile
import shutil
import time

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

def clear_directory(directory: Path) -> List[str]:
    """Remove all files in directory. Returns list of files that could not be deleted.
    Uses small retry and rename fallback to handle transient locks on Windows.
    """
    failures: List[str] = []
    for file in directory.glob("*"):
        if not file.is_file():
            continue
        ok = False
        # Try unlink with brief retries
        for _ in range(2):
            try:
                file.unlink()
                ok = True
                break
            except PermissionError:
                time.sleep(0.05)
            except Exception:
                break
        if not ok:
            # Fallback: try rename then delete
            try:
                tmp = file.with_suffix(file.suffix + ".deleting")
                if tmp.exists():
                    tmp.unlink(missing_ok=True)  # type: ignore[arg-type]
                file.rename(tmp)
                tmp.unlink()
                ok = True
            except Exception:
                failures.append(file.name)
    return failures
