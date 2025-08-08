import os
import google.generativeai as genai
import os
from dotenv import load_dotenv
from typing import Generator
from prompts import get_healthcare_system_prompt

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Configure model with healthcare-focused system instruction
system_instruction = get_healthcare_system_prompt()
model = genai.GenerativeModel(
    "gemini-2.0-flash",
    system_instruction=system_instruction
)

def get_answer(question: str, context: str = "") -> str:
    """Get answer from Gemini with optional context (legacy function)"""
    return get_answer_with_context(question, context)

def get_answer_with_context(prompt: str, context: str = "") -> str:
    """Get answer from Gemini with enhanced context handling"""
    try:
        if context:
            full_prompt = f"{prompt}\n\nContext from medical documents:\n{context}"
        else:
            full_prompt = prompt
        
        response = model.generate_content(
            full_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                top_p=0.8,
                top_k=40,
                max_output_tokens=1024,
            )
        )
        return response.text
    except Exception as e:
        print(f"[gemini_client] Error: {e}")
        return "I apologize, but I'm experiencing some technical difficulties right now. Please try asking your question again in a moment."

def get_streaming_answer(prompt: str, context: str = "") -> Generator[str, None, None]:
    """Get streaming answer from Gemini for real-time responses"""
    try:
        if context:
            full_prompt = f"{prompt}\n\nContext from medical documents:\n{context}"
        else:
            full_prompt = prompt
        
        response = model.generate_content(
            full_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                top_p=0.8,
                top_k=40,
                max_output_tokens=1024,
            ),
            stream=True
        )
        
        for chunk in response:
            if chunk.text:
                yield chunk.text
                
    except Exception as e:
        print(f"[gemini_client] Streaming error: {e}")
        yield "I apologize, but I'm experiencing some technical difficulties right now. Please try asking your question again in a moment."

def get_summary(text: str, document_name: str = "") -> str:
    """Get summary of text using Gemini with healthcare focus"""
    doc_ref = f" from {document_name}" if document_name else ""
    prompt = f"""Please provide a comprehensive yet concise summary of the following medical text{doc_ref}. 
    
    Focus on:
    - Key medical conditions or topics discussed
    - Important findings or recommendations  
    - Treatment options or procedures mentioned
    - Any significant medical data or statistics
    
    Please structure your response in a clear, easy-to-understand format while maintaining medical accuracy.
    
    Medical Text:
    {text}"""
    
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.6,
                top_p=0.8,
                max_output_tokens=512,
            )
        )
        return response.text
    except Exception as e:
        print(f"[gemini_client] Summary error: {e}")
        return "I'm unable to generate a summary at this time. Please try again later."

def check_healthcare_relevance(text: str) -> bool:
    """Check if text is healthcare-related using Gemini"""
    prompt = f"""Is the following text related to healthcare, medicine, medical conditions, treatments, or medical research? 
    Respond with only 'YES' or 'NO'.
    
    Text: {text[:500]}"""  # Limit text for efficiency
    
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=10,
            )
        )
        return "YES" in response.text.upper()
    except Exception as e:
        print(f"[gemini_client] Healthcare check error: {e}")
        return True  # Default to allowing if check fails

def get_polite_healthcare_redirect(question: str) -> str:
    """Generate a polite redirect for non-healthcare questions"""
    prompt = f"""The user asked: "{question}"
    
    This question is not related to healthcare. Please provide a polite, friendly response that:
    1. Acknowledges their question
    2. Explains that you're designed for healthcare topics
    3. Offers to help with any health-related questions
    4. Maintains a warm, helpful tone
    
    Keep the response brief and conversational."""
    
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.8,
                max_output_tokens=150,
            )
        )
        return response.text
    except Exception as e:
        print(f"[gemini_client] Redirect error: {e}")
        from prompts import get_polite_rejection
        return get_polite_rejection()
