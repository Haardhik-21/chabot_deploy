from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class Chunk(BaseModel):
    content: str
    source: str
    embedding: List[float] = None
    pdf_name: str = None
    chunk: str = None
    filename: str = None
    page_number: Optional[int] = None
    chunk_index: Optional[int] = None

class QuestionRequest(BaseModel): question: str

class AnswerResponse(BaseModel):
    answer: str
    sources: Optional[List[str]] = None
    references: Optional[List[dict]] = None

class StreamingResponse(BaseModel):
    chunk: str
    is_final: bool = False
    sources: Optional[List[str]] = None

class PDFUploadResponse(BaseModel):
    message: str
    filenames: List[str]
    total_files: int
    healthcare_files: List[str]
    rejected_files: List["RejectedFile"] = []

class RejectedFile(BaseModel):
    filename: str
    reason: str

class FileInfo(BaseModel):
    filename: str
    size: int
    upload_date: datetime
    chunks_count: int
    is_healthcare: bool

class FilesListResponse(BaseModel):
    files: List[FileInfo]
    total_files: int
    total_chunks: int

class DeletePDFRequest(BaseModel): filename: str

class DeleteResponse(BaseModel):
    message: str
    success: bool

class HealthCheckResponse(BaseModel):
    status: str
    message: str
    uploaded_files: int
