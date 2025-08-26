import re
import time
from typing import Optional, Dict, Any, List
from collections import OrderedDict
import httpx
from config import Config
from tmdb_client import (
    search_movie as tmdb_search_movie,
    get_credits as tmdb_get_credits,
    get_credits_by_imdb as tmdb_get_credits_by_imdb,
)

OMDB_URL = "http://www.omdbapi.com/"
LAST_TITLE: Optional[str] = None  # simple in-memory cache for conversational follow-ups

# --- Lightweight in-memory caches (best-effort, process-local) ---
_OMDB_CACHE: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
_TMDB_IMDB_CACHE: "OrderedDict[str, List[Dict[str, str]]]" = OrderedDict()
_TMDB_TITLE_CACHE: "OrderedDict[str, List[Dict[str, str]]]" = OrderedDict()
_CACHE_MAX = 64

def _cache_get(cache: OrderedDict, key: str):
    if key in cache:
        cache.move_to_end(key)
        return cache[key]
    return None

def _cache_put(cache: OrderedDict, key: str, value):
    cache[key] = value
    cache.move_to_end(key)
    while len(cache) > _CACHE_MAX:
        cache.popitem(last=False)


def _extract_title(q: str) -> Optional[str]:
    ql = (q or "").strip()
    # Pronoun/ellipsis follow-ups: "who directed it", "what's the genre of this movie"
    if re.search(r"\b(it|this\s+(movie|film)|the\s+(movie|film))\b", ql, re.IGNORECASE):
        if LAST_TITLE:
            return LAST_TITLE
    # Try quoted titles first
    m = re.search(r'"([^"]+)"', ql)
    if m:
        return m.group(1).strip()
    # Common patterns: cast of X, genre of X, rating of X, who directed X, hero of X
    patterns = [
        r"(?:cast|genre|rating|ratings|director|hero|heroine|actors?|actress|plot|story|synopsis|summary|runtime|duration|box\s+office|gross|collection)\s+(?:of|for|in)\s+(.+)$",
        r"(?:what\s+is\s+)?(?:the\s+)?(?:cast|genre|rating|plot|story|synopsis|summary)s?\s+(?:of|for)\s+(.+)$",
        r"who\s+(?:directed|stars?\s+in)\s+(.+)$",
    ]
    for p in patterns:
        m = re.search(p, ql, re.IGNORECASE)
        if m:
            return m.group(1).strip().rstrip("?.! ")
    # Fallback: last capitalized phrase with words
    tokens = re.findall(r"[A-Z][A-Za-z0-9'&:\-]+(?:\s+[A-Z][A-Za-z0-9'&:\-]+)*", q)
    if tokens:
        return tokens[-1].strip()
    # Last resort: try everything after 'about'
    m = re.search(r"about\s+(.+)$", ql, re.IGNORECASE)
    if m:
        return m.group(1).strip().rstrip("?.! ")
    return None


def _omdb_get(params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    key = getattr(Config, "ENTERTAINMENT_API_KEY", "")
    if not key:
        return None
    query = {**params, "apikey": key}
    try:
        with httpx.Client(timeout=5) as client:
            r = client.get(OMDB_URL, params=query)
            if r.status_code != 200:
                return None
            data = r.json()
            if not data or str(data.get("Response", "")).lower() != "true":
                return None
            return data
    except Exception:
        return None


def _fetch_movie(title: str, plot_full: bool = False) -> Optional[Dict[str, Any]]:
    global LAST_TITLE
    # Cache key (include plot_full flag to allow longer plot caching separately)
    ck = f"{title.strip().lower()}|full={bool(plot_full)}"
    cached = _cache_get(_OMDB_CACHE, ck)
    if cached:
        LAST_TITLE = cached.get("Title") or title
        return cached
    # Try exact title first
    params = {"t": title}
    if plot_full:
        params["plot"] = "full"
    data = _omdb_get(params)
    if data:
        LAST_TITLE = data.get("Title") or title
        _cache_put(_OMDB_CACHE, ck, data)
        return data
    # Try search and pick best match
    search = _omdb_get({"s": title})
    if search and isinstance(search.get("Search"), list) and search["Search"]:
        best = search["Search"][0]
        t2 = best.get("Title")
        if t2:
            params2 = {"t": t2}
            if plot_full:
                params2["plot"] = "full"
            data2 = _omdb_get(params2)
            if data2:
                LAST_TITLE = data2.get("Title") or t2
                _cache_put(_OMDB_CACHE, ck, data2)
            return data2
    return None


def _rating_from(data: Dict[str, Any], source: str) -> Optional[str]:
    for r in data.get("Ratings", []) or []:
        if str(r.get("Source", "")).lower() == source.lower():
            return r.get("Value")
    return None


def _tmdb_cast(title: str, year: Optional[int]) -> List[Dict[str, str]]:
    """Fetch cast with character names from TMDb. Returns list of {name, character}."""
    try:
        ck = f"{title.strip().lower()}|{str(year) if year else ''}"
        cached = _cache_get(_TMDB_TITLE_CACHE, ck)
        if cached is not None:
            return cached
        y = None
        if year:
            try:
                y = int(str(year)[:4])  # handle ranges like 2009–2011
            except Exception:
                y = None
        movie_id = tmdb_search_movie(title, year=y)
        if not movie_id:
            _cache_put(_TMDB_TITLE_CACHE, ck, [])
            return []
        res = tmdb_get_credits(movie_id)[:20]
        _cache_put(_TMDB_TITLE_CACHE, ck, res)
        return res
    except Exception:
        return []


def get_entertainment_answer(q: str) -> Optional[str]:
    """Return a human, multi-sentence answer for entertainment queries using OMDb + TMDb.
    Uses OMDb for title/year/genre/director/ratings/plot and TMDb for cast with character names.
    None if not answerable.
    """
    title = _extract_title(q)
    start = time.monotonic()
    deadline = 8.0  # seconds overall budget for the hybrid path

    ql = (q or "").lower()

    ask_cast = bool(re.search(r"\bcast\b|\bactors?\b|\bstarring\b|\bhero(?:ine)?\b", ql))
    ask_genre = bool(re.search(r"\bgenre\b", ql))
    ask_ratings = bool(re.search(r"\brating|ratings|imdb|rotten\b", ql))
    ask_director = bool(re.search(r"\bdirect(?:ed|or)\b", ql))
    ask_plot = bool(re.search(r"\b(plot|story|synopsis|summary)\b", ql))
    ask_runtime = bool(re.search(r"\b(runtime|duration|how long)\b", ql))
    ask_box = bool(re.search(r"\b(box office|gross|collection)\b", ql))
    top_billed_only = bool(re.search(r"\b(top\s+billed|top\s+cast\s+only)\b", ql))
    no_specific = not (ask_cast or ask_genre or ask_ratings or ask_director or ask_plot or ask_runtime or ask_box)

    # If no explicit title but it's a follow-up like "runtime" / "box office", use LAST_TITLE if available
    if not title and LAST_TITLE and (ask_cast or ask_genre or ask_ratings or ask_director or ask_plot or ask_runtime or ask_box):
        title = LAST_TITLE
    if not title:
        return None

    # Fetch OMDb data now that title is resolved
    data = _fetch_movie(title)
    if not data:
        return None

    # If plot is asked, refetch with full plot (if initial didn't include it)
    if ask_plot and (not data.get("Plot") or data.get("Plot") == "N/A" or len(data.get("Plot", "")) < 150):
        data_full = _fetch_movie(title, plot_full=True)
        if data_full:
            data = data_full

    title_out = data.get("Title") or title
    year = data.get("Year") if data.get("Year") not in (None, "N/A") else None
    genre = data.get("Genre") if data.get("Genre") not in (None, "N/A") else None
    director = data.get("Director") if data.get("Director") not in (None, "N/A") else None
    actors = data.get("Actors") if data.get("Actors") not in (None, "N/A") else None
    plot = data.get("Plot") if data.get("Plot") not in (None, "N/A") else None
    runtime = data.get("Runtime") if data.get("Runtime") not in (None, "N/A") else None
    box_office = data.get("BoxOffice") if data.get("BoxOffice") not in (None, "N/A") else None

    # Prepare cast list: prefer TMDb with roles; fall back to OMDb actors
    # Try TMDb by imdbID first (more reliable match), then fallback to title/year search
    tmdb_cast: List[Dict[str, str]] = []
    imdb_id = data.get("imdbID")
    if isinstance(imdb_id, str) and imdb_id.startswith("tt"):
        cached = _cache_get(_TMDB_IMDB_CACHE, imdb_id)
        if cached is not None:
            tmdb_cast = cached
        else:
            # Only attempt if within deadline budget
            if (time.monotonic() - start) < deadline:
                tmdb_cast = tmdb_get_credits_by_imdb(imdb_id)
                _cache_put(_TMDB_IMDB_CACHE, imdb_id, tmdb_cast)
            else:
                tmdb_cast = []
    # Fallback to title search if still needed and time remains
    if not tmdb_cast and (time.monotonic() - start) < deadline:
        tmdb_cast = _tmdb_cast(title_out, year)
    cast_with_roles: List[str] = []
    if tmdb_cast:
        # Deduplicate by actor name
        seen = set()
        for m in tmdb_cast:
            name = m.get("name")
            char = m.get("character")
            if not name or not char:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            cast_with_roles.append(f"{name} as {char}")
        # Trim to top 8 (or top 5 if explicitly asked top billed only)
        cast_with_roles = cast_with_roles[:5] if top_billed_only else cast_with_roles[:8]
    cast_fmt = None
    if cast_with_roles:
        cast_fmt = "; ".join(cast_with_roles)
    elif actors:
        # Fallback simple list
        cast_list = [a.strip() for a in actors.split(',') if a.strip()]
        limit = 5 if top_billed_only else 5
        cast_fmt = ", ".join(cast_list[:limit]) if cast_list else None

    imdb = data.get("imdbRating") if data.get("imdbRating") not in (None, "N/A") else None
    rt = _rating_from(data, "Rotten Tomatoes")

    lines = []

    # If the user asked only for cast, return a clean bulleted list (no intro/extras)
    specific_flags = [ask_cast, ask_genre, ask_ratings, ask_director, ask_plot, ask_runtime, ask_box]
    if ask_cast and sum(1 for f in specific_flags if f) == 1:
        header = f"Cast of {title_out}{f' ({year})' if year else ''}:"
        bullets: List[str] = []
        if cast_with_roles:
            limit = 5 if top_billed_only else 10
            for item in cast_with_roles[:limit]:
                bullets.append(f"- {item}")
        elif actors:
            names = [a.strip() for a in (actors or "").split(',') if a.strip()]
            limit = 5 if top_billed_only else 10
            for n in names[:limit]:
                bullets.append(f"- {n}")
        if not bullets:
            return None
        return "\n".join([header] + bullets)

    # Otherwise, include a short intro and any specifically asked details
    intro_bits = [title_out]
    if year:
        intro_bits.append(f"({year})")
    if genre and director:
        lines.append(f"{' '.join(intro_bits)} is a {genre} film directed by {director}.")
    elif genre:
        lines.append(f"{' '.join(intro_bits)} is a {genre} film.")
    elif director:
        lines.append(f"{' '.join(intro_bits)} was directed by {director}.")
    else:
        lines.append(" ".join(intro_bits) + ".")

    # Cast line (when asked, or if little else was asked)
    if ask_cast or (no_specific and cast_fmt):
        if cast_with_roles:
            lines.append(f"Notable cast and roles: {cast_fmt}.")
        elif cast_fmt:
            lines.append(f"Top cast includes {cast_fmt}.")

    # Director line (if explicitly asked and not already said)
    if ask_director and director:
        if not any("directed" in l for l in lines):
            lines.append(f"It was directed by {director}.")

    # Genre line
    if ask_genre and genre:
        lines.append(f"Genre: {genre}.")

    # Runtime line
    if ask_runtime and runtime:
        lines.append(f"Runtime: {runtime}.")

    # Ratings line
    if ask_ratings and (imdb or rt):
        rating_bits = []
        if imdb:
            rating_bits.append(f"IMDb {imdb}/10")
        if rt:
            rating_bits.append(f"Rotten Tomatoes {rt}")
        if rating_bits:
            lines.append("Ratings: " + ", ".join(rating_bits) + ".")

    # Plot (explicitly when asked, or only if nothing else specific was asked)
    if ask_plot and plot:
        lines.append(plot)
    elif no_specific and plot:
        lines.append(plot)

    # Extras for richness only for generic ask (avoid polluting specific queries)
    if no_specific and (imdb or rt) and not (top_billed_only):
        if not any(l.startswith("Ratings:") for l in lines):
            bits = []
            if imdb:
                bits.append(f"IMDb {imdb}/10")
            if rt:
                bits.append(f"Rotten Tomatoes {rt}")
            if bits:
                lines.append("Ratings: " + ", ".join(bits) + ".")

    # Box office: only when asked explicitly, or in generic overviews
    if box_office and (ask_box or no_specific):
        lines.append(f"Box office: {box_office}.")

    # Final tidy up
    out = " ".join([s.strip() for s in lines if s and s.strip()])
    return out if out else None
