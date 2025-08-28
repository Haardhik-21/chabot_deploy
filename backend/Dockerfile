FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# System deps for PDFs/OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tesseract-ocr \
    poppler-utils \
 && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# App source
COPY . .

# If using env-driven tesseract path:
# ENV TESSERACT_CMD=/usr/bin/tesseract

# Safe defaults to reduce memory/thread spikes (can be overridden in Render env)
ENV OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    TOKENIZERS_PARALLELISM=false \
    TESSERACT_CMD=/usr/bin/tesseract

EXPOSE 8000
# Use a single worker to avoid duplicate model loads and reduce memory usage
# Use Render's dynamic PORT if provided; default to 8000 locally
# Enable proxy headers for Cloudflare/Render and limit concurrency to reduce overload
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --limit-concurrency 2 --timeout-keep-alive 5 --proxy-headers --forwarded-allow-ips='*'"]