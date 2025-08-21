from pathlib import Path
from typing import List
import io
import csv

# Optional imports guarded to keep file small and avoid load errors at runtime
try:
    import docx2txt  # for .docx
except Exception:  # pragma: no cover
    docx2txt = None

try:
    import openpyxl  # for .xlsx
except Exception:  # pragma: no cover
    openpyxl = None

from pdf_parser import extract_text_from_pdf  # uses native text + OCR fallback


def _read_txt(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return path.read_text(errors="ignore")


def _read_csv(path: Path) -> str:
    lines: List[str] = []
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        for row in csv.reader(f):
            lines.append(",".join([c.strip() for c in row]))
    return "\n".join(lines)


def _read_xlsx(path: Path) -> str:
    if openpyxl is None:
        return ""
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    text_parts: List[str] = []
    for ws in wb.worksheets:
        text_parts.append(f"# Sheet: {ws.title}")
        for row in ws.iter_rows(values_only=True):
            cells = [str(c) if c is not None else "" for c in row]
            text_parts.append(" | ".join(cells))
    return "\n".join(text_parts)


def _read_docx(path: Path) -> str:
    if docx2txt is None:
        return ""
    return docx2txt.process(str(path)) or ""


def extract_text(file_path: str) -> str:
    """Return plain text for supported docs. Keep this tiny and centralized.
    Supported: pdf, docx, txt, csv, xlsx. Unknown types return empty string.
    """
    p = Path(file_path)
    ext = p.suffix.lower()

    if ext == ".pdf":
        return extract_text_from_pdf(str(p)) or ""
    if ext == ".docx":
        return _read_docx(p)
    if ext == ".txt":
        return _read_txt(p)
    if ext == ".csv":
        return _read_csv(p)
    if ext == ".xlsx":
        return _read_xlsx(p)

    # Unsupported types -> empty string; caller may decide to OCR images later if desired
    return ""
