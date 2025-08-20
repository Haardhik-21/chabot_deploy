import fitz  # PyMuPDF
from PIL import Image
import pytesseract
import io

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF with OCR fallback for image-based pages."""
    text = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc, 1):
            if page_text := page.get_text().strip():
                text.append(page_text)
            else:  # OCR fallback for image-based pages
                pix = page.get_pixmap(dpi=300)
                # Convert Pixmap to PIL Image via PNG bytes (robust across versions)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                text.append(pytesseract.image_to_string(img))
                print(f"[pdf] OCR used on page {i}")
    return "\n".join(text)
