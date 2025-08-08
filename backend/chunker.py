import re
from typing import List, Dict, Any
from embedding import get_embedding, embed_chunks

def chunk_text(text: str, filename: str, chunk_size: int = 400, overlap: int = 100) -> List[Dict[str, Any]]:
    """Enhanced text chunking with better sentence boundary detection"""
    if not text or not text.strip():
        return []
    
    # Clean and normalize text
    text = clean_text(text)
    
    # Try sentence-based chunking first
    sentences = split_into_sentences(text)
    if len(sentences) > 1:
        chunks = create_sentence_based_chunks(sentences, filename, chunk_size, overlap)
    else:
        # Fallback to word-based chunking
        chunks = create_word_based_chunks(text, filename, chunk_size, overlap)
    
    # Add embeddings to all chunks
    chunks = embed_chunks(chunks)
    
    print(f"[chunker] Created {len(chunks)} chunks for {filename}")
    return chunks

def clean_text(text: str) -> str:
    """Clean and normalize text content"""
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove special characters but keep medical notation
    text = re.sub(r'[^\w\s.,;:!?()\-\/\%°]', ' ', text)
    # Fix common PDF extraction issues
    text = re.sub(r'\b([a-z])([A-Z])', r'\1 \2', text)  # Fix concatenated words
    return text.strip()

def split_into_sentences(text: str) -> List[str]:
    """Split text into sentences using medical-aware patterns"""
    # Medical abbreviations that shouldn't end sentences
    medical_abbrevs = ['Dr.', 'Mr.', 'Mrs.', 'Ms.', 'Prof.', 'vs.', 'etc.', 'i.e.', 'e.g.', 
                      'mg.', 'ml.', 'cm.', 'mm.', 'kg.', 'lb.', 'Inc.', 'Ltd.', 'Co.']
    
    # First, protect abbreviations by temporarily replacing them
    protected_text = text
    replacements = {}
    
    for i, abbrev in enumerate(medical_abbrevs):
        placeholder = f"__ABBREV_{i}__"
        protected_text = protected_text.replace(abbrev, placeholder)
        replacements[placeholder] = abbrev
    
    # Split on sentence endings
    sentences = re.split(r'[.!?]+\s+', protected_text)
    
    # Restore abbreviations
    restored_sentences = []
    for sentence in sentences:
        for placeholder, abbrev in replacements.items():
            sentence = sentence.replace(placeholder, abbrev)
        restored_sentences.append(sentence)
    
    # Filter out very short sentences and clean up
    sentences = [s.strip() for s in restored_sentences if len(s.strip()) > 20]
    return sentences

def create_sentence_based_chunks(sentences: List[str], filename: str, target_size: int, overlap: int) -> List[Dict[str, Any]]:
    """Create chunks based on sentence boundaries"""
    chunks = []
    current_chunk = []
    current_length = 0
    
    for i, sentence in enumerate(sentences):
        sentence_length = len(sentence.split())
        
        # If adding this sentence would exceed target size, finalize current chunk
        if current_length + sentence_length > target_size and current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunks.append(create_chunk_dict(chunk_text, filename, len(chunks)))
            
            # Start new chunk with overlap
            overlap_sentences = get_overlap_sentences(current_chunk, overlap)
            current_chunk = overlap_sentences + [sentence]
            current_length = sum(len(s.split()) for s in current_chunk)
        else:
            current_chunk.append(sentence)
            current_length += sentence_length
    
    # Add final chunk if it has content
    if current_chunk:
        chunk_text = ' '.join(current_chunk)
        chunks.append(create_chunk_dict(chunk_text, filename, len(chunks)))
    
    return chunks

def create_word_based_chunks(text: str, filename: str, chunk_size: int, overlap: int) -> List[Dict[str, Any]]:
    """Fallback word-based chunking"""
    words = text.split()
    chunks = []
    
    for i in range(0, len(words), chunk_size - overlap):
        chunk_words = words[i:i + chunk_size]
        chunk_text = ' '.join(chunk_words)
        chunks.append(create_chunk_dict(chunk_text, filename, len(chunks)))
    
    return chunks

def get_overlap_sentences(sentences: List[str], overlap_words: int) -> List[str]:
    """Get sentences for overlap based on word count"""
    overlap_sentences = []
    word_count = 0
    
    # Take sentences from the end until we reach overlap word count
    for sentence in reversed(sentences):
        sentence_words = len(sentence.split())
        if word_count + sentence_words <= overlap_words:
            overlap_sentences.insert(0, sentence)
            word_count += sentence_words
        else:
            break
    
    return overlap_sentences

def create_chunk_dict(text: str, filename: str, chunk_index: int) -> Dict[str, Any]:
    """Create standardized chunk dictionary"""
    return {
        "text": text.strip(),
        "source": filename,
        "filename": filename,
        "chunk_index": chunk_index,
        "word_count": len(text.split()),
        "char_count": len(text),
        "preview": text[:100] + "..." if len(text) > 100 else text
    }

def chunk_by_sections(text: str, filename: str) -> List[Dict[str, Any]]:
    """Chunk text by detecting sections/headers (useful for structured documents)"""
    # Detect section headers (lines that are short and may be titles)
    lines = text.split('\n')
    sections = []
    current_section = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Heuristic: if line is short and next line exists, might be a header
        if len(line.split()) <= 8 and len(line) < 100:
            # Finalize current section
            if current_section:
                section_text = ' '.join(current_section)
                if len(section_text.split()) > 50:  # Only keep substantial sections
                    sections.append(section_text)
            current_section = [line]  # Start new section with header
        else:
            current_section.append(line)
    
    # Add final section
    if current_section:
        section_text = ' '.join(current_section)
        if len(section_text.split()) > 50:
            sections.append(section_text)
    
    # Convert sections to chunks
    chunks = []
    for i, section in enumerate(sections):
        chunks.append(create_chunk_dict(section, filename, i))
    
    return embed_chunks(chunks) if chunks else chunk_text(text, filename)
