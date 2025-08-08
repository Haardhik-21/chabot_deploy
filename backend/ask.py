from vector_store import load_all_uploaded_chunks, search_similar_chunks
from embedding import get_embedding
from gemini_client import get_answer_with_context, get_streaming_answer
from utils import is_healthcare_text
from prompts import (
    get_polite_rejection, get_no_documents_message, get_summary_prompt,
    get_context_prompt, format_response_with_references
)
import re
from typing import Dict, List, Any, Generator

# Store conversation context for follow-up questions
conversation_context = []

def answer_question(question: str, stream: bool = False) -> str:
    """Answer a question based on uploaded healthcare documents"""
    print(f"[ask.py] Question: {question}")
    
    # Load all chunks
    chunks = load_all_uploaded_chunks()
    if not chunks:
        return get_no_documents_message()

    # Handle different types of questions
    if is_summary_question(question):
        return handle_summary_question(question, chunks)
    
    # Check if question is healthcare-related (but allow document questions)
    if not is_document_related_question(question) and not is_healthcare_related_question(question):
        return get_polite_rejection()
    
    # Handle general Q&A with context
    return handle_general_question(question, chunks, stream)

def answer_question_stream(question: str) -> Generator[str, None, None]:
    """Stream answer for real-time response"""
    print(f"[ask.py] Streaming Question: {question}")
    
    chunks = load_all_uploaded_chunks()
    if not chunks:
        yield get_no_documents_message()
        return

    # Handle summary questions first
    if is_summary_question(question):
        yield handle_summary_question(question, chunks)
        return

    # Check if question is healthcare-related (but allow document questions)
    if not is_document_related_question(question) and not is_healthcare_related_question(question):
        yield get_polite_rejection()
        return

    # Check if this is a compound question
    if is_compound_question(question):
        # For compound questions, get the full response first, then stream it
        full_response = handle_compound_question(question, chunks)
        
        # Stream the response word by word for better UX
        words = full_response.split()
        current_chunk = ""
        
        for i, word in enumerate(words):
            current_chunk += word + " "
            
            # Send chunks of ~5-10 words for smooth streaming
            if (i + 1) % 8 == 0 or i == len(words) - 1:
                yield current_chunk
                current_chunk = ""
        
        return
    
    # Handle single questions with normal streaming
    query_embedding = get_embedding(question)
    top_chunks = search_similar_chunks(query_embedding, k=5)
    
    if not top_chunks:
        yield "I couldn't find relevant information in your uploaded healthcare documents. Could you try rephrasing your question or upload additional medical documents?"
        return

    # Prepare context and sources
    context = "\n\n".join([chunk.get("text", "") for chunk in top_chunks])
    sources = list(set([chunk.get("source", "Unknown") for chunk in top_chunks]))
    
    # Add to conversation context
    add_to_context(question, context, sources)
    
    # Create enhanced prompt
    prompt = get_context_prompt(question, context, sources)
    
    # Stream the response
    response_parts = []
    for chunk in get_streaming_answer(prompt):
        response_parts.append(chunk)
        yield chunk
    
    # Add references at the end
    full_response = ''.join(response_parts)
    reference_text = format_reference_section(sources)
    yield reference_text

def is_summary_question(question: str) -> bool:
    """Detect if the question is asking for a summary"""
    summary_keywords = [
        "what is this pdf about", "what are the pdfs about", "summarize",
        "summary of", "what does this document", "what do these documents",
        "overview of", "main points", "key information", "tell me about",
        "what is in", "contents of", "about this document", "document summary"
    ]
    return any(keyword in question.lower() for keyword in summary_keywords)

def is_document_related_question(question: str) -> bool:
    """Check if question is about the documents themselves"""
    document_keywords = [
        "pdf", "document", "file", "paper", "report", "study", 
        "what is this about", "what does this say", "contents",
        "summary", "overview", "main points", "key information"
    ]
    return any(keyword in question.lower() for keyword in document_keywords)

def is_healthcare_related_question(question: str) -> bool:
    """AI-powered healthcare question detection using Gemini classification"""
    # Use Gemini AI for intelligent healthcare question classification
    try:
        from gemini_client import check_healthcare_relevance
        result = check_healthcare_relevance(question)
        print(f"[ask] Gemini question classification: {result}")
        return result
    except Exception as e:
        print(f"[ask] Error checking healthcare relevance: {e}")
        # Conservative fallback: reject if we can't classify
        return False

def handle_summary_question(question: str, chunks: List[Dict]) -> str:
    """Handle document summarization requests"""
    # Group chunks by source
    summaries = {}
    for chunk in chunks:
        source = chunk.get("source", "Unknown Document")
        summaries.setdefault(source, []).append(chunk.get("text", ""))
    
    if "what is this pdf about" in question.lower() and len(summaries) == 1:
        # Single document summary
        source = list(summaries.keys())[0]
        content = "\n\n".join(summaries[source][:5])  # Limit content
        prompt = get_summary_prompt(source)
        response = get_answer_with_context(prompt, content)
        return format_response_with_references(response, [source])
    
    elif "what are the pdfs about" in question.lower() or len(summaries) > 1:
        # Multiple documents summary
        combined_summaries = []
        all_sources = []
        
        for source, content_list in summaries.items():
            content = "\n\n".join(content_list[:3])  # Limit per document
            prompt = get_summary_prompt(source)
            summary = get_answer_with_context(prompt, content)
            combined_summaries.append(f"**{source}:**\n{summary}")
            all_sources.append(source)
        
        final_response = "Here's a summary of your uploaded healthcare documents:\n\n" + "\n\n".join(combined_summaries)
        return format_response_with_references(final_response, all_sources)
    
    # Fallback to general summary
    return handle_general_question(question, chunks)

def handle_general_question(question: str, chunks: List[Dict]) -> str:
    """Handle general Q&A questions, including compound questions"""
    # Check if this is a compound question (multiple topics)
    if is_compound_question(question):
        return handle_compound_question(question, chunks)
    
    # Handle single topic question
    return handle_single_question(question, chunks)

def is_compound_question(question: str) -> bool:
    """Detect if question contains multiple topics/conditions"""
    question_lower = question.lower()
    
    # Strong compound indicators
    strong_indicators = [
        " and ", " & ", "both ", " also ", " plus ", " as well as ",
        "tell me about both", "compare", "difference between", "versus", " vs "
    ]
    
    # Check for strong compound indicators
    has_strong_compound = any(indicator in question_lower for indicator in strong_indicators)
    
    # Check for multiple disease/condition names
    common_conditions = [
        "malaria", "cold", "fever", "flu", "diabetes", "hypertension", 
        "cancer", "pneumonia", "asthma", "tuberculosis", "covid", "dengue",
        "typhoid", "hepatitis", "migraine", "arthritis", "bronchitis"
    ]
    
    condition_count = sum(1 for condition in common_conditions if condition in question_lower)
    
    # Check for multiple medical terms in different contexts
    medical_contexts = [
        "symptoms of", "treatment for", "causes of", "prevention of",
        "diagnosis of", "medication for", "therapy for", "cure for"
    ]
    
    context_count = sum(1 for context in medical_contexts if context in question_lower)
    
    # It's compound if:
    # 1. Has strong compound words, OR
    # 2. Multiple conditions mentioned, OR  
    # 3. Multiple medical contexts (like "symptoms of X and treatment for Y")
    is_compound = has_strong_compound or condition_count >= 2 or context_count >= 2
    
    print(f"[ask] Question analysis: compound={is_compound}, strong_indicators={has_strong_compound}, conditions={condition_count}, contexts={context_count}")
    
    return is_compound

def handle_compound_question(question: str, chunks: List[Dict]) -> str:
    """Handle questions with multiple topics by searching broadly and organizing by source"""
    # Split question into parts and search more broadly
    query_parts = extract_question_parts(question)
    
    # Search with higher k value to get more diverse results
    query_embedding = get_embedding(question)
    top_chunks = search_similar_chunks(query_embedding, k=10, threshold=0.2)
    
    if not top_chunks:
        return "I couldn't find relevant information in your uploaded healthcare documents. Could you try rephrasing your question or upload additional medical documents?"
    
    # Group chunks by source document
    chunks_by_source = {}
    for chunk in top_chunks:
        source = chunk.get("source", "Unknown")
        if source not in chunks_by_source:
            chunks_by_source[source] = []
        chunks_by_source[source].append(chunk)
    
    # Generate response for each relevant document
    document_responses = []
    all_sources = []
    
    for source, source_chunks in chunks_by_source.items():
        # Create context from chunks of this document
        source_context = "\n\n".join([chunk.get("text", "") for chunk in source_chunks[:3]])
        
        # Create a focused prompt for this document
        prompt = get_document_specific_prompt(question, source_context, source)
        
        # Get response for this document
        response = get_answer_with_context(prompt, source_context)
        
        if response and len(response.strip()) > 50:  # Only include substantial responses
            document_responses.append({
                'source': source,
                'response': response.strip()
            })
            all_sources.append(source)
    
    if not document_responses:
        return "I couldn't find relevant information to answer your question in the uploaded documents."
    
    # Combine responses with clear source attribution
    final_response = combine_document_responses(document_responses, question)
    
    # Add sources at the end
    return format_response_with_references(final_response, all_sources)

def extract_question_parts(question: str) -> List[str]:
    """Extract different parts of a compound question"""
    # Simple splitting on common conjunctions
    parts = []
    
    # Split on 'and', 'also', etc.
    import re
    split_pattern = r'\s+(?:and|also|plus|as well as|&)\s+'
    parts = re.split(split_pattern, question, flags=re.IGNORECASE)
    
    return [part.strip() for part in parts if part.strip()]

def get_document_specific_prompt(question: str, context: str, source: str) -> str:
    """Create a prompt focused on a specific document"""
    return f"""You are a healthcare assistant. Answer the relevant parts of this question using ONLY the information from the provided medical document.

Question: {question}

Medical Document Content:
{context}

Instructions:
- Answer only the parts of the question that this document covers
- Use simple, clear language
- Be direct and concise
- Don't mention page numbers or document references
- If this document doesn't cover part of the question, simply don't address that part
- Keep your response focused and professional"""

def combine_document_responses(document_responses: List[Dict], original_question: str) -> str:
    """Combine responses from multiple documents with clear attribution"""
    if len(document_responses) == 1:
        return document_responses[0]['response']
    
    # Create a clean, structured response
    combined_parts = []
    
    for i, doc_resp in enumerate(document_responses):
        source = doc_resp['source']
        response = doc_resp['response'].strip()
        
        # Clean up the response
        response = clean_response_text(response)
        
        # Create clean source name
        source_name = source.replace('.pdf', '').replace('_', ' ').replace('-', ' ').title()
        
        # Add numbered sections for clarity
        section_number = i + 1
        combined_parts.append(f"{section_number}. **{source_name}:**\n{response}")
    
    return "\n\n".join(combined_parts)

def clean_response_text(response: str) -> str:
    """Clean up response text to remove unwanted formatting"""
    # Remove page references
    response = re.sub(r'\(Page \d+\)', '', response)
    response = re.sub(r'\(Pages \d+-\d+\)', '', response)
    
    # Remove asterisks and bold formatting
    response = re.sub(r'\*\*([^*]+)\*\*', r'\1', response)
    response = re.sub(r'\*([^*]+)\*', r'\1', response)
    
    # Remove "Please remember" disclaimers (we'll add our own)
    response = re.sub(r'\*\*Please remember\*\*:.*?(?=\n|$)', '', response, flags=re.IGNORECASE | re.DOTALL)
    response = re.sub(r'Please remember:.*?(?=\n|$)', '', response, flags=re.IGNORECASE | re.DOTALL)
    
    # Clean up multiple spaces and newlines
    response = re.sub(r'\s+', ' ', response)
    response = response.strip()
    
    return response

def handle_single_question(question: str, chunks: List[Dict]) -> str:
    """Handle single topic questions"""
    # Get relevant chunks
    query_embedding = get_embedding(question)
    top_chunks = search_similar_chunks(query_embedding, k=5)
    
    if not top_chunks:
        return "I couldn't find relevant information in your uploaded healthcare documents. Could you try rephrasing your question or upload additional medical documents?"

    # Prepare context and sources
    context = "\n\n".join([chunk.get("text", "") for chunk in top_chunks])
    sources = list(set([chunk.get("source", "Unknown") for chunk in top_chunks]))
    
    # Add to conversation context
    add_to_context(question, context, sources)
    
    # Check for follow-up context
    previous_context = get_recent_context()
    
    # Create enhanced prompt
    if previous_context:
        from prompts import get_follow_up_prompt
        prompt = get_follow_up_prompt(question, previous_context, context)
    else:
        prompt = get_context_prompt(question, context, sources)
    
    # Get response
    response = get_answer_with_context(prompt, context)
    
    # Format with references
    return format_response_with_references(response, sources)

def add_to_context(question: str, context: str, sources: List[str]):
    """Add question and context to conversation history"""
    global conversation_context
    conversation_context.append({
        "question": question,
        "context": context[:500],  # Limit context size
        "sources": sources,
        "timestamp": __import__('time').time()
    })
    
    # Keep only last 5 interactions
    if len(conversation_context) > 5:
        conversation_context = conversation_context[-5:]

def get_recent_context() -> str:
    """Get recent conversation context for follow-up questions"""
    if not conversation_context:
        return ""
    
    # Get last 2 interactions
    recent = conversation_context[-2:]
    context_parts = []
    
    for item in recent:
        context_parts.append(f"Previous Q: {item['question']}")
        context_parts.append(f"Context: {item['context'][:200]}...")  # Truncate
    
    return "\n".join(context_parts)

def format_reference_section(sources: List[str]) -> str:
    """Format the reference section for streaming responses"""
    if not sources:
        return "\n\nPlease consult with your healthcare provider for personalized medical advice."
    
    # Clean and deduplicate sources
    clean_sources = list(set([s.strip() for s in sources if s.strip()]))
    
    if len(clean_sources) == 1:
        ref_text = f"\n\nSource: {clean_sources[0]}"
    else:
        ref_text = f"\n\nSources: {', '.join(clean_sources)}"
    
    return ref_text + "\n\nPlease consult with your healthcare provider for personalized medical advice."

def clear_conversation_context():
    """Clear conversation context (useful for new sessions)"""
    global conversation_context
    conversation_context = []
