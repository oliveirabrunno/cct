"""
Google Images via SerpAPI — fotos recentes com filtro de temporada.
Requer SERPAPI_KEY no .env (plano gratuito: 100 buscas/mês).

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


def search_cc_player_photo(player_name: str, year: int = None, tournament_name: str = None) -> dict | None:
    """Busca uma foto CC do jogador no Google Images via SerpAPI."""
    if not SERPAPI_KEY:
        log.debug("SERPAPI_KEY não definida — Google Images pulado")
        return None

    season  = _get_season()
    queries = SEASON_QUERIES.get(season, SEASON_QUERIES["hard"])

    target_year = year or CURRENT_YEAR
    
    if tournament_name:
        queries = [
            f"{{player}} tennis {tournament_name} {target_year}",
            f"{{player}} tennis {tournament_name} action"
        ]
    else:
        queries = SEASON_QUERIES.get(season, SEASON_QUERIES["hard"])

    for query_tpl in queries:
        query = query_tpl.format(player=player_name, year=target_year)
        params = {
            "q":       query,
            "tbm":     "isch",
            "api_key": SERPAPI_KEY,
            "num":     5,
        }
        try:
            resp = requests.get("https://serpapi.com/search", params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log.warning(f"SerpAPI falhou ({query!r}): {e}")
            continue

        images = data.get("images_results", [])
        if not images:
            continue

        # Pega a primeira imagem com resolução mínima aceitável
        for img in images:
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

    log.debug(f"Google Images: nenhuma foto encontrada para '{player_name}'")
    return None


def search_player_images(player_name: str, count: int = 4, year: int = None, tournament_name: str = None) -> list[dict]:
    """Retorna múltiplas fotos CC do jogador para variedade de slides."""
    if not SERPAPI_KEY:
        return []

    target_year = year or CURRENT_YEAR
    
    if tournament_name:
        query = f"{player_name} tennis {tournament_name} {target_year}"
    else:
        season = _get_season()
        query = SEASON_QUERIES.get(season, SEASON_QUERIES["hard"])[0].format(
            player=player_name, year=target_year
        )
    params = {
        "q":       query,
        "tbm":     "isch",
        "api_key": SERPAPI_KEY,
        "num":     10,
    }
    try:
        resp = requests.get("https://serpapi.com/search", params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.warning(f"SerpAPI multi-search falhou: {e}")
        return []

    results = []
    for img in data.get("images_results", []):
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

    return results
