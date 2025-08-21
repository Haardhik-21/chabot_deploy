from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any
import os

# Local imports
from models import QuestionRequest, PDFUploadResponse
from response import generate_streaming_response
from context import clear_conversation_context
from chunker import chunk_text
from extractors import extract_text
from vector_core import (
    save_chunks_to_store, delete_chunks_for_file,
    clear_all_chunks, load_all_uploaded_chunks
)
from config import Config
from file_utils import save_uploaded_file, cleanup_file, clear_directory
from urllib.parse import unquote
from scraper import scrape_to_chunks
from vector_core import save_chunks_to_web_store, list_web_sources, delete_web_source

# Initialize directories
Config.init_dirs()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def process_file(file: UploadFile) -> Dict[str, Any]:
    """Process a single uploaded file (pdf/docx/xlsx/csv/txt, etc.) and return chunks or error."""
    path = Config.UPLOAD_DIR / file.filename
    try:
        # Save uploaded file
        save_uploaded_file(file, Config.UPLOAD_DIR)

        # Unified text extraction (PDFs do native+OCR via pdf_parser)
        text = ""
        try:
            text = extract_text(str(path)) or ""
        except Exception as e:
            print(f"[upload] extract_text failed for {file.filename}: {e}")

        # Chunk (chunker will OCR if text is empty and file is a PDF)
        chunks = chunk_text(text, str(path))
        if not chunks:
            return {"error": "No valid chunks extracted"}

        return {"chunks": chunks, "filename": file.filename}

    except Exception as e:
        return {"error": f"Error processing file: {str(e)}"}
    finally:
        if path.exists() and "error" in locals():
            cleanup_file(path)

@app.post("/upload/", response_model=PDFUploadResponse)
async def upload_files(files: List[UploadFile] = File(...)):
    # Use files present on disk as the source of truth for the upload limit (all types)
    existing_on_disk = {f.name for f in Config.UPLOAD_DIR.glob("*")}
    if (total := len(existing_on_disk) + len(files)) > Config.MAX_FILES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Maximum {Config.MAX_FILES} files allowed. "
                f"You can upload {Config.MAX_FILES - len(existing_on_disk)} more."
            )
        )

    results = {"healthcare_files": [], "rejected_files": []}
    all_chunks = []

    for file in files:
        if file.filename in existing_on_disk:
            continue
        
        if result := process_file(file):
            if "error" in result:
                results["rejected_files"].append({
                    "filename": file.filename, 
                    "reason": result["error"]
                })
            else:
                all_chunks.extend(result["chunks"])
                results["healthcare_files"].append(file.filename)

    if all_chunks:
        save_chunks_to_store(all_chunks)

    return {
        "message": "Files processed successfully",
        "filenames": results["healthcare_files"],  # This is the required field
        "healthcare_files": results["healthcare_files"],
        "rejected_files": results["rejected_files"],
        "total_files": len(existing_on_disk) + len(results["healthcare_files"])
    }


@app.post("/ingest-url")
async def ingest_url(payload: Dict[str, Any]):
    """Scrape a URL and store chunks in a separate web collection.
    Does not affect PDF flow or existing retrieval behavior.
    """
    url = (payload or {}).get("url", "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="Missing 'url'")

    try:
        chunks = await scrape_to_chunks(url)
        if not chunks:
            return {"message": "No extractable content found", "url": url, "stored": 0}
        saved = save_chunks_to_web_store(chunks)
        if not saved:
            raise RuntimeError("Failed to store scraped content")
        return {"message": "Ingested successfully", "url": url, "stored": len(chunks)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ingest URL: {e}")


@app.get("/web-sources")
async def get_web_sources():
    """List ingested web URLs and their chunk counts (separate collection)."""
    return list_web_sources()


@app.delete("/web-sources")
async def delete_web_source_endpoint(payload: Dict[str, Any]):
    url = (payload or {}).get("url", "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="Missing 'url'")
    ok = delete_web_source(url)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to delete web source")
    return {"message": "Deleted", "url": url}


@app.post("/files/delete/{filename}")
async def delete_file(filename: str):
    # Decode URL-encoded names and normalize to base filename
    decoded = unquote(filename)
    safe_name = os.path.basename(decoded)
    filepath = Config.UPLOAD_DIR / safe_name
    cleanup_file(filepath)
    delete_chunks_for_file(safe_name)
    # Clear conversation context so answers don't use stale history
    try:
        clear_conversation_context()
    except Exception as _:
        pass
    return {"message": f"Deleted {safe_name}"}


@app.delete("/clear-all/")
async def clear_all():
    locked = clear_directory(Config.UPLOAD_DIR)
    clear_all_chunks()
    # Reset conversation context when repository is emptied
    try:
        clear_conversation_context()
    except Exception as _:
        pass
    resp = {"message": "All data cleared.", "locked_files": locked}
    return resp


@app.post("/ask")
async def ask(data: QuestionRequest):
    """Handle streaming question responses with proper formatting"""
    return StreamingResponse(
        generate_streaming_response(data.question),
        media_type="text/plain"  # Using text/plain for cleaner output
    )


@app.get("/new-session/")
async def new_session():
    clear_conversation_context()
    return {"message": "New conversation session started"}


@app.get("/files/")
async def list_files():
    """Summarize uploaded files and chunk counts from Qdrant for UI display."""
    try:
        records = load_all_uploaded_chunks(limit=2000)
        # Group by filename
        by_file: Dict[str, Dict[str, Any]] = {}
        for r in records:
            p = r.get("payload", {}) or {}
            fname = p.get("filename") or p.get("source") or p.get("file") or "unknown"
            if fname not in by_file:
                by_file[fname] = {"filename": fname, "chunk_count": 0, "sample_text": None}
            by_file[fname]["chunk_count"] += 1
            if not by_file[fname]["sample_text"] and p.get("text"):
                txt = p.get("text", "")
                by_file[fname]["sample_text"] = (txt[:180] + ("..." if len(txt) > 180 else ""))
        # Only include files that currently exist on disk to avoid stale entries (all types)
        existing_on_disk = {f.name for f in Config.UPLOAD_DIR.glob("*")}
        files = sorted([f for f in by_file.keys() if f in existing_on_disk])
        file_details = [by_file[k] for k in files]
        return {
            "files": files,
            "total_files": len(files),
            "total_chunks": sum(item["chunk_count"] for item in file_details),
            "file_details": file_details,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list files: {e}")

 
