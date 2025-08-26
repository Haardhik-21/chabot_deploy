import httpx
from typing import Optional, Dict, Any, List
from config import Config

TMDB_API = "https://api.themoviedb.org/3"


def _client() -> httpx.Client:
    is_bearer = bool(Config.TMDB_API_KEY and Config.TMDB_API_KEY.startswith("eyJ"))
    headers = {"Authorization": f"Bearer {Config.TMDB_API_KEY}"} if is_bearer else {}
    mode = "bearer" if is_bearer else "api_key"
    try:
        # Lightweight one-time log per process creation
        print(f"[tmdb] client init mode={mode}")
    except Exception:
        pass
    # TMDb supports either Bearer (v4 auth) or api_key query param. We'll use api_key if not bearer.
    return httpx.Client(timeout=5, headers=headers)


def _params(extra: Dict[str, Any] = None) -> Dict[str, Any]:
    # Prefer api_key when no Bearer token provided
    p = {"api_key": Config.TMDB_API_KEY} if Config.TMDB_API_KEY and not Config.TMDB_API_KEY.startswith("eyJ") else {}
    if extra:
        p.update(extra)
    return p


def search_movie(title: str, year: Optional[int] = None) -> Optional[int]:
    try:
        with _client() as c:
            params = _params({"query": title})
            if year:
                params["year"] = year
            r = c.get(f"{TMDB_API}/search/movie", params=params)
            if r.status_code != 200:
                print(f"[tmdb] search_movie failed: {r.status_code} {r.text[:120]}")
                return None
            data = r.json()
            results = data.get("results") or []
            if not results:
                print(f"[tmdb] search_movie no results for title='{title}' year={year}")
                return None
            mid = int(results[0].get("id"))
            print(f"[tmdb] search_movie hit id={mid} for '{title}'")
            return mid
    except Exception:
        return None


def get_credits(movie_id: int) -> List[Dict[str, Any]]:
    try:
        with _client() as c:
            r = c.get(f"{TMDB_API}/movie/{movie_id}/credits", params=_params())
            if r.status_code != 200:
                print(f"[tmdb] get_credits failed: {r.status_code} {r.text[:120]}")
                return []
            data = r.json()
            cast = data.get("cast") or []
            # Return list of {name, character}
            out = []
            for m in cast:
                name = m.get("name") or m.get("original_name")
                character = m.get("character")
                if name and character:
                    out.append({"name": name, "character": character})
            print(f"[tmdb] get_credits movie_id={movie_id} cast_len={len(out)}")
            return out
    except Exception:
        return []


def get_credits_by_imdb(imdb_id: str) -> List[Dict[str, Any]]:
    try:
        with _client() as c:
            r = c.get(f"{TMDB_API}/find/{imdb_id}", params=_params({"external_source": "imdb_id"}))
            if r.status_code != 200:
                print(f"[tmdb] find by imdb failed: {r.status_code} {r.text[:120]}")
                return []
            data = r.json()
            results = (data.get("movie_results") or [])
            if not results:
                print(f"[tmdb] find by imdb: no movie_results for {imdb_id}")
                return []
            movie_id = results[0].get("id")
            if not movie_id:
                print(f"[tmdb] find by imdb: missing id for {imdb_id}")
                return []
            return get_credits(int(movie_id))
    except Exception:
        return []
