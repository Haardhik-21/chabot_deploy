import fitz  # PyMuPDF
from PIL import Image
import pytesseract
import io

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF with OCR fallback for image-based pages."""
    text = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc, 1):
            page_text = page.get_text().strip()
            # If page has no or very little native text, also OCR the image
            do_ocr = len(page_text) == 0 or len(page_text) < 300
            if do_ocr:
                # Lower DPI to reduce memory footprint on small instances
                pix = page.get_pixmap(dpi=200)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                ocr_text = (pytesseract.image_to_string(img, config="--oem 3 --psm 6") or "").strip()
                if page_text and ocr_text:
                    # Merge when both exist (mixed page). Keep minimal duplication.
                    merged = page_text
                    if ocr_text not in merged:
                        merged = merged + "\n" + ocr_text
                    text.append(merged)
                elif ocr_text:
                    text.append(ocr_text)
                else:
                    text.append(page_text)
                print(f"[pdf] OCR used on page {i}{' (mixed)' if page_text else ''}")
            else:
                text.append(page_text)
    return "\n".join(text)
