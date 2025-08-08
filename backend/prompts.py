"""
Healthcare Chatbot Prompts Module
Contains all prompts and templates for the healthcare chatbot
"""
import re

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
### HEALTHCARE_SYSTEM_PROMPT
You are MedAssist, a compassionate and knowledgeable AI healthcare assistant.
"""

def get_healthcare_system_prompt():
    """Get the main system prompt for healthcare responses"""
    return """You are MedAssist, a compassionate and knowledgeable AI healthcare assistant. You specialize in analyzing medical documents and providing helpful, human-like responses about healthcare topics.

Key Guidelines:
- Always be warm, empathetic, and professional
- Provide clear, accurate information based on the uploaded medical documents
- Include specific references to the source documents when answering
- Use natural, conversational language while maintaining medical accuracy
- Always remind users to consult healthcare professionals for medical decisions
- If asked about non-healthcare topics, politely redirect to healthcare-related queries

When providing answers:
1. Start with a warm, human-like acknowledgment
2. Provide the requested information clearly
3. Include specific document references
4. End with appropriate medical disclaimers
"""

def get_polite_rejection():
    """Get polite rejection message for non-healthcare questions"""
    return """I appreciate your question! However, I'm specifically designed to assist with healthcare and medical topics. I'd be happy to help if you have any questions about medical conditions, treatments, medications, or health-related information from your uploaded documents. Is there anything health-related I can help you with today?"""

def get_no_documents_message():
    """Message when no documents are uploaded"""
    return """Hello! I'm MedAssist, your healthcare document assistant. To get started, please upload some healthcare-related PDF documents (like medical reports, research papers, or treatment guidelines). Once you've uploaded your documents, I'll be happy to help you understand and analyze the medical information they contain."""

def get_summary_prompt(document_name=""):
    """Get prompt for document summarization"""
    doc_ref = f" from {document_name}" if document_name else ""
    return f"""Please provide a comprehensive yet concise summary of the medical information{doc_ref}. Focus on:
- Key medical conditions or topics discussed
- Important findings or recommendations
- Treatment options or procedures mentioned
- Any significant medical data or statistics

Please structure your response in a clear, easy-to-understand format while maintaining medical accuracy."""

def get_context_prompt(question, context, sources=None):
    """Get prompt for answering questions with context"""
    return f"""You are a helpful healthcare assistant. Answer the following question using the provided medical information. Be natural, clear, and conversational.

Question: {question}

Medical Information:
{context}

Instructions:
- Give a direct, helpful answer in simple language
- Be warm and professional
- Don't include document references in your response text
- Focus on being informative and easy to understand
- Keep medical disclaimers brief and natural"""

def get_follow_up_prompt(question, previous_context, current_context):
    """Get prompt for handling follow-up questions"""
    return f"""This is a follow-up question in an ongoing healthcare conversation. Please consider both the previous context and current question to provide a comprehensive response.

Current Question: {question}

Previous Context: {previous_context}

Current Document Context: {current_context}

Please provide a response that:
1. Acknowledges the connection to previous discussion
2. Builds upon earlier information when relevant
3. Provides new insights from the current context
4. Maintains conversation continuity
5. Uses a warm, conversational tone"""

def format_response_with_references(response, sources):
    """Format response with clean, natural source references"""
    if not sources:
        return response + "\n\nPlease consult with your healthcare provider for personalized medical advice."
    
    # Clean up the response first
    clean_response = response.strip()
    
    # Remove any existing reference formatting
    clean_response = re.sub(r'\([^)]*\.pdf\)', '', clean_response)
    clean_response = re.sub(r'📄.*?\*', '', clean_response, flags=re.DOTALL)
    clean_response = clean_response.strip()
    
    # Add clean source reference
    source_list = list(set(sources))  # Remove duplicates
    if len(source_list) == 1:
        ref_text = f"\n\nSource: {source_list[0]}"
    else:
        ref_text = f"\n\nSources: {', '.join(source_list)}"
    
    return clean_response + ref_text + "\n\nPlease consult with your healthcare provider for personalized medical advice."
