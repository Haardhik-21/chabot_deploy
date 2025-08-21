"""
Prompts Module (domain-agnostic)
Contains prompts and templates for a general document QA assistant
"""
import re
from system_prompt import SYSTEM_PROMPT

def load_prompts():
    """Load prompts from prompts.txt file"""
    try:
        with open('prompts.txt', 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except FileNotFoundError:
        return get_default_prompts()

def get_default_prompts():
    """Fallback prompts if file is not found"""
    return """
### SYSTEM_PROMPT
You are a helpful, concise, and human-like document assistant. Use the provided document excerpts to answer clearly without fabricating details.
"""

def get_healthcare_system_prompt():
    """Get the main system prompt for healthcare responses"""
    # Legacy alias for backward compatibility; prefer importing SYSTEM_PROMPT directly
    return SYSTEM_PROMPT
# Note: legacy healthcare-specific notes removed.

def get_polite_rejection():
    """Get polite rejection message for non-healthcare questions"""
    return """I focus on answering using your uploaded documents and ingested web pages. Could you ask a question related to those?"""

def get_no_documents_message():
    """Message when no documents are uploaded"""
    return """Hello! Please upload some PDF documents or ingest a web URL to get started. After that, ask any question and I'll answer using the content provided."""

def get_summary_prompt(document_name=""):
    """Get prompt for document summarization"""
    doc_ref = f" from {document_name}" if document_name else ""
    return f"""Please provide a concise summary of the document{doc_ref}. Focus on:
- Key topics discussed
- Important findings or recommendations
- Notable data points or sections

Structure the response clearly and keep it easy to understand."""

def get_context_prompt(question, context, sources=None):
    """Get prompt for answering questions with context"""
    source_info = f"\nSource Document: {sources[0]}" if sources else ""
    
    return f"""You are a helpful document assistant answering using the provided excerpts.
    
Document Information:{source_info}

Question: {question}

Relevant Document Content:
{context}

Instructions for your response (STRICT):
1. Start with a clear, direct answer (if the question is a definition like "what is X", provide a brief definition first)
2. Include specific details from the provided excerpts, and avoid hallucinating
3. If the document doesn't contain the answer, say so clearly
4. Use natural, human language; be warm and professional
5. Do NOT include any "Sources:" text in the body; it will be appended separately by the system
6. Output MUST be plain text. Do NOT use Markdown formatting (no **bold**, no lists/bullets, no headings).
7. Preserve names exactly as they appear in the excerpts; do not alter or stylize them.
8. When enumerating multiple people/items, place each on a new line as plain text.
9. If the user asks multiple different sub-questions in one message (e.g., about different topics like a disease, a person, and policies), answer each sub-question in its own paragraph, labeled succinctly (e.g., "Pneumonia:", "Sekhar Kammula:", "Policies/Publications:") with a single blank line between paragraphs. Do not use numbered or bulleted lists.

Now, provide a helpful response to the user's question based on the document content above:"""

def get_follow_up_prompt(question, previous_context, current_context):
    """Get prompt for handling follow-up questions"""
    return f"""This is a follow-up question in an ongoing conversation. Consider both the previous context and current question.

Current Question: {question}

Previous Context: {previous_context}

Current Document Context: {current_context}

Please provide a response that:
1. Acknowledges the connection to previous discussion
2. Builds upon earlier information when relevant
3. Provides new insights from the current context
4. Maintains conversation continuity
5. Uses a warm, conversational tone"""

def get_document_specific_prompt(question: str, context: str, source: str) -> str:
    """Create a focused prompt for a specific document."""
    return f"""Answer this question using ONLY the provided document:
    
    Question: {question}
    
    Document Content:
    {context}
    
    Instructions:
    - Be clear and concise
    - Only answer what's in the document
    - Keep it professional and focused"""

def format_response_with_references(response, sources):
    """Format response with clean, natural source references"""
    if not sources:
        return response
        
    # Remove any existing reference markers
    response = re.sub(r'\s*\[\d+\]', '', response)
    
    # Add natural source references
    if len(sources) == 1:
        return f"{response}\n\nSource: {sources[0]}"
    else:
        return f"{response}\n\nSources: {', '.join(sources)}"

# New small helpers for basic interactions
def get_greeting_response():
    return (
        "Hello! I can help you explore your uploaded PDFs and ingested web pages. "
        "Upload a file or ingest a URL, then ask your question (e.g., 'Summarize page 2' or 'What does this section say about eligibility?')."
    )

def get_help_response():
    return (
        "Try: 'Summarize the uploaded PDF', 'List the key points', or 'Explain the section on requirements'."
    )

def get_definition_prompt(question: str, sources=None):
    """Prompt optimized to define a term first, then add details from context."""
    source_info = f" based on {sources[0]}" if sources else ""
    return (
        f"Provide a concise definition of the concept asked in the question{source_info}.\n"
        f"Question: {question}\n\n"
        "Strict instructions:\n"
        "- Output ONLY a concise definition in 2–3 sentences, human-friendly and professional.\n"
        "- Do NOT include extra sections unless explicitly asked.\n"
        "- Do NOT use bullet points, lists, or headings.\n"
        "- If the document does not define it directly, say so and provide the closest relevant explanation from the excerpts."
    )
