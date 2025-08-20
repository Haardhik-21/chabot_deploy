import os
from typing import Dict, Any, List
import httpx
import trafilatura
from urllib.parse import urlparse
from chunker import chunk_text

DEFAULT_UA = os.getenv(
    "USER_AGENT",
    # Realistic desktop Chrome UA to reduce 403s
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "15"))
MAX_CRAWL_SIZE = int(os.getenv("MAX_CRAWL_SIZE", "200000"))


def _is_valid_url(url: str) -> bool:
    try:
        p = urlparse(url)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False


async def fetch_and_extract(url: str) -> str:
    if not _is_valid_url(url):
        raise ValueError("Invalid URL")

    headers = {
        "User-Agent": DEFAULT_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Dest": "document",
        "Upgrade-Insecure-Requests": "1",
    }
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=REQUEST_TIMEOUT, headers=headers) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content = resp.text[:MAX_CRAWL_SIZE]
    except httpx.HTTPStatusError as e:
        # Fallback: let trafilatura handle fetching (sometimes bypasses 403 w/ its own logic)
        if e.response is not None and e.response.status_code == 403:
            downloaded = trafilatura.fetch_url(url, no_ssl=False)
            if downloaded:
                extracted = trafilatura.extract(downloaded, include_comments=False, include_tables=False, favor_recall=True) or ""
                return extracted.strip()
        raise

    # Use trafilatura to extract main content
    extracted = trafilatura.extract(content, include_comments=False, include_tables=False, favor_recall=True) or ""
    return extracted.strip()


async def scrape_to_chunks(url: str) -> List[Dict[str, Any]]:
    """Fetch a URL, extract readable text, then chunk it using existing pipeline.
    The chunk filename/source is set to the URL so attribution remains clean.
    """
    text = await fetch_and_extract(url)
    if not text:
        return []
    # Reuse existing chunking + embedding flow
    chunks = chunk_text(text, url)
    # Ensure payload marks this as web content without changing existing schema usage
    for c in chunks:
        md = c.get("metadata") or {}
        md["source_type"] = "web"
        c["metadata"] = md
    return chunks
