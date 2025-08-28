from fastapi import FastAPI, UploadFile, File, HTTPException, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any
import os
from urllib.parse import unquote

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
from scraper import scrape_to_chunks
from vector_core import save_chunks_to_web_store, list_web_sources, delete_web_source, has_web_content
from intents import is_entertainment_question, is_greeting, is_help, is_smalltalk

# Import logger
from logger import logger

# Initialize directories
Config.init_dirs()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request, call_next):
    try:
        logger.info(f"[req] {request.method} {request.url.path}")
        response = await call_next(request)
        logger.info(f"[res] {request.method} {request.url.path} -> {response.status_code}")
        return response
    except Exception as e:
        logger.exception(f"[req] unhandled error on {request.method} {request.url.path}: {e}")
        raise


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
            logger.error(f"[upload] extract_text failed for {file.filename}: {e}")

        # Chunk (chunker will OCR if text is empty and file is a PDF)
        chunks = chunk_text(text, str(path))
        if not chunks:
            return {"error": "No valid chunks extracted"}

        return {"chunks": chunks, "filename": file.filename}

    except Exception as e:
        logger.exception(f"[upload] Error processing file {file.filename}: {e}")
        return {"error": f"Error processing file: {str(e)}"}
    finally:
        if path.exists() and "error" in locals():
            cleanup_file(path)


def _background_ingest(saved_filenames: List[str]) -> None:
    try:
        logger.info(f"[bg] ingest start for {len(saved_filenames)} file(s)")
        all_chunks: List[Dict[str, Any]] = []
        accepted: List[str] = []
        rejected: List[Dict[str, Any]] = []
        for fname in saved_filenames:
            try:
                p = Config.UPLOAD_DIR / fname
                # Re-run extraction and chunking from disk
                text = ""
                try:
                    text = extract_text(str(p)) or ""
                except Exception as e:
                    logger.error(f"[bg] extract_text failed for {fname}: {e}")
                chunks = chunk_text(text, str(p))
                if not chunks:
                    rejected.append({"filename": fname, "reason": "No valid chunks extracted"})
                    continue
                all_chunks.extend(chunks)
                accepted.append(fname)
            except Exception as e:
                logger.exception(f"[bg] processing failed for {fname}: {e}")
                rejected.append({"filename": fname, "reason": str(e)})
        if all_chunks:
            try:
                logger.info(f"[bg] saving {len(all_chunks)} chunk(s) to vector store")
                ok = save_chunks_to_store(all_chunks)
                if not ok:
                    logger.error("[bg] vector store save returned False")
            except Exception as e:
                logger.exception(f"[bg] vector save failed: {e}")
        logger.info(f"[bg] ingest done: accepted={len(accepted)} rejected={len(rejected)}")
    except Exception as e:
        logger.exception(f"[bg] unexpected failure: {e}")


@app.post("/upload/", response_model=PDFUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_files(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    logger.info(f"[upload] request received: {len(files) if files else 0} file(s)")
    existing_on_disk = {f.name for f in Config.UPLOAD_DIR.glob("*")}
    if (total := len(existing_on_disk) + len(files)) > Config.MAX_FILES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Maximum {Config.MAX_FILES} files allowed. "
                f"You can upload {Config.MAX_FILES - len(existing_on_disk)} more."
            )
        )

    saved_filenames: List[str] = []
    rejected_files: List[Dict[str, Any]] = []
    for file in files:
        try:
            logger.info(f"[upload] saving: {file.filename}")
            if file.filename in existing_on_disk:
                # Overwrite existing with latest
                cleanup_file(Config.UPLOAD_DIR / file.filename)
            save_uploaded_file(file, Config.UPLOAD_DIR)
            saved_filenames.append(file.filename)
        except Exception as e:
            logger.exception(f"[upload] failed to save {file.filename}: {e}")
            rejected_files.append({"filename": file.filename, "reason": f"Save failed: {e}"})

    if saved_filenames:
        background_tasks.add_task(_background_ingest, saved_filenames)

    resp = {
        "message": "Files accepted for processing",
        "filenames": saved_filenames,
        "healthcare_files": saved_filenames,
        "rejected_files": rejected_files,
        "total_files": len(existing_on_disk) + len(saved_filenames)
    }
    logger.info(f"[upload] accepted={len(saved_filenames)} rejected={len(rejected_files)} (processing in background)")
    return resp


@app.post("/ingest-url")
async def ingest_url(payload: Dict[str, Any]):
    url = (payload or {}).get("url", "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="Missing 'url'")

    try:
        chunks = await scrape_to_chunks(url)
        if not chunks:
            logger.info(f"[ingest-url] No content found for {url}")
            return {"message": "No extractable content found", "url": url, "stored": 0}
        saved = save_chunks_to_web_store(chunks)
        if not saved:
            raise RuntimeError("Failed to store scraped content")
        logger.info(f"[ingest-url] Ingested {url} with {len(chunks)} chunks")
        return {"message": "Ingested successfully", "url": url, "stored": len(chunks)}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[ingest-url] Failed for {url}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to ingest URL: {e}")


@app.get("/web-sources")
async def get_web_sources():
    return list_web_sources()


@app.delete("/web-sources")
async def delete_web_source_endpoint(payload: Dict[str, Any]):
    url = (payload or {}).get("url", "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="Missing 'url'")
    ok = delete_web_source(url)
    if not ok:
        logger.error(f"[web-sources] Failed to delete {url}")
        raise HTTPException(status_code=500, detail="Failed to delete web source")
    logger.info(f"[web-sources] Deleted {url}")
    return {"message": "Deleted", "url": url}


@app.post("/files/delete/{filename}")
async def delete_file(filename: str):
    decoded = unquote(filename)
    safe_name = os.path.basename(decoded)
    filepath = Config.UPLOAD_DIR / safe_name
    cleanup_file(filepath)
    delete_chunks_for_file(safe_name)
    try:
        clear_conversation_context()
    except Exception:
        logger.warning(f"[delete_file] Failed to clear context for {safe_name}")
    logger.info(f"[delete_file] Deleted {safe_name}")
    return {"message": f"Deleted {safe_name}"}


@app.delete("/clear-all/")
async def clear_all():
    locked = clear_directory(Config.UPLOAD_DIR)
    clear_all_chunks()
    try:
        clear_conversation_context()
    except Exception:
        logger.warning("[clear-all] Failed to clear conversation context")
    logger.info("[clear-all] All data cleared")
    return {"message": "All data cleared.", "locked_files": locked}


@app.post("/ask")
async def ask(data: QuestionRequest):
    """Handle streaming question responses with entertainment/domain gating"""
    allow = False
    ql = (data.question or "").strip()
    if is_greeting(ql) or is_help(ql) or is_smalltalk(ql):
        allow = True

    ent_on = getattr(data, "entertainment_enabled", False)
    omdb_key = bool(getattr(Config, "ENTERTAINMENT_API_KEY", ""))
    tmdb_key = bool(getattr(Config, "TMDB_API_KEY", ""))
    if ent_on:
        allow = True

    if not allow:
        has_files = any(Config.UPLOAD_DIR.glob("*"))
        if has_files or has_web_content():
            allow = True

    if not allow:
        logger.warning(
            f"[ask] gate blocked. ent_on={ent_on} omdb_key={omdb_key} "
            f"tmdb_key={tmdb_key} has_files={any(Config.UPLOAD_DIR.glob('*'))} "
            f"has_web={has_web_content()} q='{(data.question or '')[:80]}'"
        )
        raise HTTPException(
            status_code=400,
            detail="No sources available. Enable Entertainment mode, or upload documents / ingest a URL."
        )

    return StreamingResponse(
        generate_streaming_response(data.question, entertainment_enabled=ent_on),
        media_type="text/plain"
    )


@app.get("/new-session/")
async def new_session():
    clear_conversation_context()
    logger.info("[session] New conversation session started")
    return {"message": "New conversation session started"}


@app.get("/files/")
async def list_files():
    try:
        records = load_all_uploaded_chunks(limit=2000)
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
        logger.exception(f"[list_files] Failed to list files: {e}")
        raise HTTPException(status_code=500, detail="Failed to list files. Check backend logs.")
