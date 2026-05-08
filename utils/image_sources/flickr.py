"""
Flickr como fonte de imagens de jogadores — fotos CC recentes de torneios.
Requer FLICKR_API_KEY no .env (gratuito: flickr.com/services/api/key.gne).

Busca por nome do jogador + contexto de temporada + ano atual.
Aceita apenas CC BY (4), CC BY-SA (5), CC0 (9), Public Domain (10).
"""

import os
import re
import requests
from datetime import date
from utils.logger import get_logger

log = get_logger(__name__)

FLICKR_API    = "https://api.flickr.com/services/rest/"
FLICKR_API_KEY = os.getenv("FLICKR_API_KEY", "")

# Licenças aceitas (livres para uso editorial/atribuição)
ACCEPTED_LICENSES = {"4", "5", "9", "10"}  # CC BY, CC BY-SA, CC0, PD
LICENSE_NAMES = {
    "4":  "CC BY 2.0",
    "5":  "CC BY-SA 2.0",
    "9":  "CC0",
    "10": "Public Domain",
}

# Palavras-chave de salas de quadra que queremos EVITAR por temporada
SEASON_BLACKLIST = {
    "clay":   ["us_open", "us open", "australian_open", "australian open", "wimbledon", "queens"],
    "grass":  ["us_open", "us open", "australian_open", "australian open"],
    "hard":   ["roland_garros", "roland garros", "clay"],
    "indoor": [],
}

SEASON_QUERIES = {
    "clay":  [
        "{player} tennis Roland Garros {year}",
        "{player} tennis clay court {year}",
        "{player} tennis Roma clay {year}",
        "{player} tennis clay",
    ],
    "grass": [
        "{player} tennis Wimbledon {year}",
        "{player} tennis grass court {year}",
        "{player} tennis grass",
    ],
    "hard":  [
        "{player} tennis US Open {year}",
        "{player} tennis Australian Open {year}",
        "{player} tennis hard court {year}",
    ],
}


def _get_season() -> str:
    month = date.today().month
    if month in (4, 5, 6):
        return "clay"
    if month in (6, 7):
        return "grass"
    return "hard"


def _is_blacklisted(photo: dict, season: str) -> bool:
    blacklist = SEASON_BLACKLIST.get(season, [])
    title = (photo.get("title", "") + " " + str(photo.get("id", ""))).lower()
    return any(kw in title for kw in blacklist)


def _photo_to_url(photo: dict) -> str | None:
    """Monta URL da foto no maior tamanho disponível."""
    # url_b = 1024px (Large), url_c = 800px (Medium 800)
    return photo.get("url_b") or photo.get("url_c") or photo.get("url_z") or None


def search_player_images(
    player_name: str,
    count: int = 6,
    season: str | None = None,
    exclude_urls: set | None = None,
) -> list[dict]:
    """
    Busca fotos CC do jogador no Flickr priorizando temporada atual.
    Retorna lista de dicts com url, license, author, source.
    """
    if not FLICKR_API_KEY:
        log.debug("FLICKR_API_KEY não configurado — Flickr desativado")
        return []

    season  = season or _get_season()
    year    = date.today().year
    exclude = exclude_urls or set()
    results: list[dict] = []
    seen_ids: set[str]  = set()

    queries = SEASON_QUERIES.get(season, SEASON_QUERIES["hard"])

    for query_tpl in queries:
        if len(results) >= count:
            break
        query = query_tpl.format(player=player_name, year=year)

        params = {
            "method":        "flickr.photos.search",
            "api_key":       FLICKR_API_KEY,
            "text":          query,
            "license":       ",".join(ACCEPTED_LICENSES),
            "sort":          "date-posted-desc",
            "content_type":  1,          # fotos apenas
            "media":         "photos",
            "extras":        "url_b,url_c,url_z,license,owner_name,date_upload,title",
            "per_page":      15,
            "format":        "json",
            "nojsoncallback": 1,
        }

        try:
            resp = requests.get(FLICKR_API, params=params, timeout=12)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log.warning(f"Flickr search falhou ({query}): {e}")
            continue

        photos = data.get("photos", {}).get("photo", [])
        for photo in photos:
            photo_id = str(photo.get("id", ""))
            if photo_id in seen_ids:
                continue

            url = _photo_to_url(photo)
            if not url or url in exclude:
                continue

            # Filtrar fotos de temporada errada pelo título
            if _is_blacklisted(photo, season):
                continue

            # Rejeitar fotos onde o sobrenome do jogador não aparece no título
            title = photo.get("title", "").lower()
            last_name = player_name.split()[-1].lower()
            if len(last_name) > 3 and last_name not in title and player_name.lower() not in title:
                continue

            seen_ids.add(photo_id)
            license_id = str(photo.get("license", ""))
            owner = photo.get("ownername", "Flickr")

            results.append({
                "url":            url,
                "license":        LICENSE_NAMES.get(license_id, f"CC license {license_id}"),
                "author":         owner,
                "source":         "flickr",
                "season_context": season,
                "title":          photo.get("title", ""),
            })

            if len(results) >= count:
                break

    if results:
        log.info(f"Flickr: {len(results)} fotos para '{player_name}' (temporada: {season})")
    else:
        log.debug(f"Flickr: nenhuma foto para '{player_name}'")

    return results
