import os
import google.generativeai as genai
from typing import Generator
from dotenv import load_dotenv
from system_prompt import SYSTEM_PROMPT

# Initialize Gemini
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.0-flash", system_instruction=SYSTEM_PROMPT)

def _get_response(prompt: str, context: str = "", stream: bool = False, **config):
    """Helper function to generate responses with common config."""
    full_prompt = f"{prompt}\n\nContext from medical documents:\n{context}" if context else prompt
    return model.generate_content(
        full_prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=config.get('temperature', 0.7),
            top_p=config.get('top_p', 0.8),
            top_k=config.get('top_k', 40),
            max_output_tokens=config.get('max_output_tokens', 1024),
        ),
        stream=stream
    )

def get_answer(question: str, context: str = "") -> str:
    """Legacy function - use get_answer_with_context instead."""
    return get_answer_with_context(question, context)

def get_answer_with_context(prompt: str, context: str = "") -> str:
    """Get answer from Gemini with optional context."""
    try:
        return _get_response(prompt, context).text
    except Exception as e:
        print(f"[gemini] Error: {e}")
        return "I'm having trouble with that request. Could you try rephrasing?"

def get_streaming_answer(prompt: str, context: str = "") -> Generator[str, None, None]:
    """Stream response from Gemini with context."""
    try:
        for chunk in _get_response(prompt, context, stream=True):
            if chunk.text:
                yield chunk.text
    except Exception as e:
        print(f"[gemini] Stream error: {e}")
        yield "I'm having trouble streaming the response. Please try again."

def get_summary(text: str, document_name: str = "") -> str:
    """Generate a healthcare-focused summary of the text."""
    try:
        prompt = f"""Summarize this {f'from {document_name} ' if document_name else ''}medical text. Focus on:
        - Key conditions/topics
        - Important findings
        - Treatment options
        - Medical data
        
        Text: {text[:15000]}"""
        
        return _get_response(prompt, max_output_tokens=512, temperature=0.6).text
    except Exception as e:
        print(f"[gemini] Summary error: {e}")
        return "Unable to generate summary. Please try again later."

def check_healthcare_relevance(text: str) -> bool:
    """Check if text is healthcare-related using Gemini."""
    try:
        prompt = f"Is this about healthcare? Respond 'yes' or 'no':\n{text[:2000]}"
        response = _get_response(prompt, temperature=0.1, max_output_tokens=10).text
        return response.strip().lower().startswith('yes')
    except Exception as e:
        print(f"[gemini] Relevance check error: {e}")
        return True

def get_polite_healthcare_redirect(question: str) -> str:
    """Generate a polite redirect for non-healthcare questions."""
    try:
        prompt = f"""As a healthcare assistant, politely decline this non-medical question in 1-2 sentences:
        Question: {question}"""
        return _get_response(prompt, max_output_tokens=100).text.strip()
    except Exception as e:
        print(f"[gemini] Redirect error: {e}")
        return "I specialize in healthcare topics. How can I assist you with medical questions?"
