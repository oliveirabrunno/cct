"""
Google Images via SerpAPI com fallback para DuckDuckGo Images.

SerpAPI requer SERPAPI_KEY no .env (plano gratuito: 100 buscas/mês).
Quando SerpAPI esgota créditos ou a key está ausente, DuckDuckGo é usado
automaticamente — sem API key, sem limite de créditos.

Busca "{player} tennis clay {year}" para fotos da temporada atual.
"""

import os
import requests
from datetime import date
from utils.logger import get_logger

log = get_logger(__name__)

SERPAPI_KEY  = os.getenv("SERPAPI_KEY", "")
CURRENT_YEAR = date.today().year

SEASON_QUERIES = {
    "clay":  [
        "{player} tennis Roland Garros {year}",
        "{player} tennis clay court {year}",
        "{player} tennis clay",
    ],
    "grass": [
        "{player} tennis Wimbledon {year}",
        "{player} tennis grass court",
    ],
    "hard":  [
        "{player} tennis US Open {year}",
        "{player} tennis hard court",
    ],
}

def _get_season() -> str:
    month = date.today().month
    if month in (4, 5, 6):
        return "clay"
    if month in (6, 7):
        return "grass"
    return "hard"


def _build_queries(player_name: str, year: int, tournament_name: str = None, search_override: str = None) -> list[str]:
    if search_override:
        return [search_override]
    if tournament_name:
        return [
            f"{player_name} tennis {tournament_name} {year}",
            f"{player_name} tennis {tournament_name} action",
        ]
    season = _get_season()
    templates = SEASON_QUERIES.get(season, SEASON_QUERIES["hard"])
    return [t.format(player=player_name, year=year) for t in templates]


def _ddg_search_images(queries: list[str], count: int = 5) -> list[dict]:
    """DuckDuckGo Images — fallback gratuito, sem API key."""
    try:
        from ddgs import DDGS
    except ImportError:
        log.debug("ddgs não instalado — DDG pulado (pip install ddgs)")
        return []

    for query in queries:
        try:
            results = []
            with DDGS() as ddgs:
                for img in ddgs.images(query, max_results=count * 3):
                    w = int(img.get("width", 0) or 0)
                    h = int(img.get("height", 0) or 0)
                    if w >= 400 and h >= 400:
                        results.append({
                            "url":     img.get("image"),
                            "width":   w,
                            "height":  h,
                            "license": "unknown",
                            "author":  img.get("source", "DuckDuckGo"),
                            "source":  "duckduckgo",
                        })
                    if len(results) >= count:
                        break
            if results:
                log.info(f"DuckDuckGo Images: '{query}' → {len(results)} fotos")
                return results
        except Exception as e:
            log.warning(f"DuckDuckGo Images falhou ({query!r}): {e}")

    return []


def _serpapi_search(query: str, num: int = 10) -> list[dict]:
    """Uma busca no SerpAPI. Retorna lista de imagens ou [] em erro/quota."""
    params = {
        "q":       query,
        "tbm":     "isch",
        "api_key": SERPAPI_KEY,
        "num":     num,
    }
    try:
        resp = requests.get("https://serpapi.com/search", params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            log.warning(f"SerpAPI erro: {data['error']}")
            return []
        return data.get("images_results", [])
    except Exception as e:
        log.warning(f"SerpAPI falhou ({query!r}): {e}")
        return []


def search_cc_player_photo(player_name: str, year: int = None, tournament_name: str = None) -> dict | None:
    """Busca uma foto do jogador. Tenta SerpAPI primeiro, cai para DuckDuckGo."""
    target_year = year or CURRENT_YEAR
    queries = _build_queries(player_name, target_year, tournament_name)

    # Tenta SerpAPI
    if SERPAPI_KEY:
        for query in queries:
            for img in _serpapi_search(query, num=5):
                w = img.get("original_width", 0)
                h = img.get("original_height", 0)
                if w >= 400 and h >= 400:
                    log.info(f"Google Images (SerpAPI): '{player_name}' — {query!r}")
                    return {
                        "url":    img.get("original"),
                        "width":  w,
                        "height": h,
                        "license": "CC",
                        "author":  img.get("source", "Google CC"),
                        "source":  "google_cc",
                    }

    # Fallback: DuckDuckGo
    results = _ddg_search_images(queries, count=1)
    if results:
        img = results[0]
        log.info(f"DuckDuckGo Images (fallback): '{player_name}'")
        return img

    log.debug(f"Nenhuma foto encontrada para '{player_name}'")
    return None


def search_player_images(player_name: str, count: int = 4, year: int = None, tournament_name: str = None, search_override: str = None) -> list[dict]:
    """Retorna múltiplas fotos do jogador. Tenta SerpAPI, cai para DuckDuckGo.

    search_override: query customizada (ex: "Alcaraz Roma Masters trophy 2026")
    """
    target_year = year or CURRENT_YEAR
    queries = _build_queries(player_name, target_year, tournament_name, search_override)

    # Tenta SerpAPI
    if SERPAPI_KEY:
        query = queries[0]
        images = _serpapi_search(query, num=10)
        results = []
        for img in images:
            w = img.get("original_width", 0)
            h = img.get("original_height", 0)
            if w >= 400 and h >= 400:
                results.append({
                    "url":    img.get("original"),
                    "width":  w,
                    "height": h,
                    "license": "CC",
                    "author":  img.get("source", "Google CC"),
                    "source":  "google_cc",
                })
            if len(results) >= count:
                break
        if results:
            return results
        log.info(f"SerpAPI sem resultados para '{player_name}' — tentando DuckDuckGo")

    # Fallback: DuckDuckGo
    return _ddg_search_images(queries, count=count)
