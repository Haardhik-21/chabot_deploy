import re
from typing import List, Dict, Any
from embedding import embed_chunks
from pdf2image import convert_from_path
import pytesseract
import os
from dotenv import load_dotenv
load_dotenv()
# Tesseract path (update if needed)
pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_CMD", "tesseract")

# Optional: Poppler path for Windows (used by pdf2image)
POPPLER_PATH = os.getenv("POPPLER_PATH")

def chunk_text(text: str, filename: str, chunk_size: int = 400, overlap: int = 140) -> List[Dict[str, Any]]:
    """Chunk text with OCR fallback for PDFs."""
    if not (text or '').strip() and os.path.exists(filename) and filename.lower().endswith(".pdf"):
        text = ocr_pdf(filename)
    
    if not (text or '').strip():
        print(f"[chunker] No text to chunk for {filename}")
        return []

    text = clean_text(text)
    sentences = split_into_sentences(text)
    chunks = (create_sentence_based_chunks if len(sentences) > 1 else create_word_based_chunks)(
        sentences if len(sentences) > 1 else text, filename, chunk_size, overlap
    )
    return embed_chunks(chunks) if chunks else []

def ocr_pdf(pdf_path: str) -> str:
    """Extract text from PDF using OCR."""
    try:
        # Use POPPLER_PATH if provided (Windows); otherwise rely on system PATH (Linux/Docker)
        images = (
            convert_from_path(pdf_path, dpi=150, poppler_path=POPPLER_PATH)
            if POPPLER_PATH
            else convert_from_path(pdf_path, dpi=150)
        )
        return "\n".join(
            page_text for img in images
            if (page_text := pytesseract.image_to_string(img).strip())
        )
    except Exception as e:
        print(f"[OCR] Error: {e}")
        return ""

def clean_text(text: str) -> str:
    """Clean and normalize text."""
    text = re.sub(r'\s+', ' ', re.sub(r'[^\w\s.,;:!?()\-\/\%°]', ' ', text))
    return re.sub(r'\b([a-z])([A-Z])', r'\1 \2', text).strip()

def split_into_sentences(text: str) -> List[str]:
    """Split text into sentences, handling common abbreviations."""
    abbrevs = ['Dr.', 'Mr.', 'Mrs.', 'Ms.', 'Prof.', 'vs.', 'etc.', 'i.e.', 'e.g.', 
              'mg.', 'ml.', 'cm.', 'mm.', 'kg.', 'lb.', 'Inc.', 'Ltd.']
    
    # Protect abbreviations
    protected = text
    for i, abbr in enumerate(abbrevs):
        protected = protected.replace(abbr, f"__ABBR_{i}__")
    
    # Split and restore abbreviations
    return [
        ' '.join(abbrevs[int(m.group(1))] if (m := re.match(r'__ABBR_(\d+)__', w)) else w 
                for w in s.split())
        for s in re.split(r'[.!?]+\s+', protected)
        if len(s.strip()) > 20
    ]

def create_sentence_based_chunks(sentences: List[str], filename: str, target_size: int, 
                               overlap: int) -> List[Dict[str, Any]]:
    chunks, current, curr_len = [], [], 0
    
    for sent in sentences:
        sent_words = sent.split()
        if curr_len + len(sent_words) > target_size and current:
            chunks.append(create_chunk(" ".join(current), filename, len(chunks)))
            current = get_overlap(current, overlap)
            curr_len = sum(len(s.split()) for s in current)
        current.append(sent)
        curr_len += len(sent_words)
    
    if current:
        chunks.append(create_chunk(" ".join(current), filename, len(chunks)))
    return chunks

def create_word_based_chunks(text: str, filename: str, chunk_size: int, 
                           overlap: int) -> List[Dict[str, Any]]:
    words = text.split()
    return [
        create_chunk(" ".join(words[i:i + chunk_size]), filename, i // (chunk_size - overlap))
        for i in range(0, len(words), chunk_size - overlap)
    ]

def get_overlap(sentences: List[str], overlap_words: int) -> List[str]:
    """Get overlapping sentences for context."""
    words, result = [], []
    for sent in reversed(sentences):
        sent_words = sent.split()
        if len(words) + len(sent_words) > overlap_words:
            needed = overlap_words - len(words)
            if needed > 0:
                result.insert(0, " ".join(sent_words[-needed:]))
            break
        result.insert(0, sent)
        words.extend(sent_words)
    return result

def create_chunk(text: str, filename: str, idx: int) -> Dict[str, Any]:
    """Create chunk dictionary with metadata."""
    base_filename = os.path.basename(filename)
    return {
        "text": text.strip(),
        "source": filename,
        "filename": base_filename,  
        "chunk_index": idx,
        "word_count": len(text.split()),
        "char_count": len(text),
        "preview": text[:100] + "..." if len(text) > 100 else text,
        "metadata": {
            "source_file": base_filename,
            "chunk_number": idx + 1
        }
    }
