from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import List
import shutil, os, json
from dotenv import load_dotenv
load_dotenv()

from models import QuestionRequest
from ask import answer_question_stream, clear_conversation_context
from pdf_parser import extract_text_from_pdf
from chunker import chunk_text
from embedding import embed_chunks
from vector_store import (
    save_chunks_to_store, load_all_uploaded_chunks, delete_chunks_for_file,
    get_uploaded_files, clear_all_chunks, store_embeddings
)
from utils import is_healthcare_text
from gemini_client import check_healthcare_relevance

UPLOAD_DIR = "uploaded_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/upload/")
async def upload_files(files: List[UploadFile] = File(...)):
    # Check current uploaded files
    existing_files = get_uploaded_files()
    total_files_after_upload = len(existing_files) + len(files)
    
    if total_files_after_upload > 3:
        raise HTTPException(
            status_code=400, 
            detail=f"Maximum 3 files allowed. You currently have {len(existing_files)} files. You can upload {3 - len(existing_files)} more files."
        )

    all_chunks = []
    healthcare_files = []
    rejected_files = []
    skipped_files = []
    
    for file in files:
        if not file.filename.lower().endswith('.pdf'):
            rejected_files.append({"filename": file.filename, "reason": "Only PDF files are supported"})
            continue
        
        # Check if file already exists
        if file.filename in existing_files:
            skipped_files.append(file.filename)
            print(f"[main] Skipped {file.filename} (already uploaded)")
            continue
            
        path = os.path.join(UPLOAD_DIR, file.filename)
        
        # Save file
        with open(path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Extract text
        text = extract_text_from_pdf(path)
        if not text.strip():
            rejected_files.append({"filename": file.filename, "reason": "Could not extract text from PDF"})
            os.remove(path)  # Remove empty file
            continue

        # Check healthcare relevance with enhanced validation
        if not is_healthcare_text(text) and not check_healthcare_relevance(text):
            print(f"[main] Rejected {file.filename} (non-healthcare content)")
            rejected_files.append({"filename": file.filename, "reason": "Content is not healthcare-related"})
            os.remove(path)  # Remove non-healthcare file
            continue

        # Process healthcare file
        chunks = chunk_text(text, file.filename)
        chunks = embed_chunks(chunks)
        all_chunks.extend(chunks)
        healthcare_files.append(file.filename)
        print(f"[main] Successfully processed {file.filename} ({len(chunks)} chunks)")

    if not all_chunks:
        error_msg = "No valid healthcare documents were uploaded. "
        if rejected_files:
            reasons = [f"{r['filename']}: {r['reason']}" for r in rejected_files]
            error_msg += "Issues found: " + "; ".join(reasons)
        raise HTTPException(status_code=400, detail=error_msg)

    # Store embeddings
    store_embeddings(all_chunks)
    
    # Build response message
    response_parts = []
    if healthcare_files:
        response_parts.append(f"Successfully uploaded {len(healthcare_files)} healthcare document(s)")
    if skipped_files:
        response_parts.append(f"{len(skipped_files)} file(s) already existed")
    if rejected_files:
        response_parts.append(f"{len(rejected_files)} file(s) rejected")
    
    response_msg = ". ".join(response_parts) if response_parts else "No files processed"
    
    # Get updated file list
    updated_files = get_uploaded_files()
    
    return {
        "message": response_msg,
        "files": healthcare_files,
        "total_files": len(updated_files),
        "healthcare_files": healthcare_files,
        "rejected_files": [r['filename'] for r in rejected_files],
        "skipped_files": skipped_files,
        "all_uploaded_files": updated_files,
        "total_chunks": len(load_all_uploaded_chunks())
    }

@app.get("/files/")
async def list_files():
    files = get_uploaded_files()
    chunks = load_all_uploaded_chunks()
    
    # Group chunks by source for detailed info
    file_details = {}
    for chunk in chunks:
        source = chunk.get("source", "unknown")
        if source not in file_details:
            file_details[source] = {
                "filename": source,
                "chunk_count": 0,
                "sample_text": ""
            }
        file_details[source]["chunk_count"] += 1
        if not file_details[source]["sample_text"]:
            file_details[source]["sample_text"] = chunk.get("text", "")[:100] + "..."
    
    return {
        "files": files,
        "total_files": len(files),
        "total_chunks": len(chunks),
        "file_details": list(file_details.values())
    }

@app.delete("/delete/{filename}")
async def delete_file(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    delete_chunks_for_file(filename)
    return {"message": f"{filename} deleted."}

@app.delete("/clear-all/")
async def clear_all():
    for f in os.listdir(UPLOAD_DIR):
        os.remove(os.path.join(UPLOAD_DIR, f))
    clear_all_chunks()
    return {"message": "All data cleared."}

@app.post("/ask/")
async def ask(data: QuestionRequest):
    """Main ask endpoint - always streams responses"""
    return StreamingResponse(
        generate_streaming_response(data.question),
        media_type="text/plain"
    )

async def generate_streaming_response(question: str):
    """Generate streaming response for real-time chat"""
    try:
        for chunk in answer_question_stream(question):
            # Send clean text chunks directly
            yield chunk
        
    except Exception as e:
        print(f"[main] Streaming error: {e}")
        yield "Sorry, I encountered an error while processing your request. Please try again."

@app.post("/new-session/")
async def new_session():
    """Clear conversation context for new session"""
    clear_conversation_context()
    return {"message": "New session started"}
