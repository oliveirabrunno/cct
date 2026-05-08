"""
Flickr — fonte primária de imagens CC de tenistas.
Queries em 4 tiers: torneio específico → superfície → tênis+ano → tênis.
Requer FLICKR_API_KEY (gratuito em flickr.com/services/apps/create).
"""

import os
import re
import requests
from datetime import date
from utils.logger import get_logger

log = get_logger(__name__)

FLICKR_API     = "https://api.flickr.com/services/rest/"
FLICKR_API_KEY = os.getenv("FLICKR_API_KEY", "")

ACCEPTED_LICENSES = {"4", "5", "9", "10"}  # CC BY, CC BY-SA, CC0, Public Domain
LICENSE_NAMES = {
    "4":  "CC BY 2.0",
    "5":  "CC BY-SA 2.0",
    "9":  "CC0",
    "10": "Public Domain",
}

# Termos de busca por nome de torneio
TOURNAMENT_TERMS = {
    "Roma":           ["Roma", "Rome", "Internazionali", "Italian Open", "Foro Italico"],
    "Roland Garros":  ["Roland Garros", "French Open", "Roland-Garros"],
    "Madrid":         ["Madrid", "Mutua Madrid", "Caja Magica"],
    "Monte-Carlo":    ["Monte Carlo", "Monte-Carlo"],
    "Wimbledon":      ["Wimbledon", "All England"],
    "US Open":        ["US Open", "Flushing"],
    "Australian Open":["Australian Open", "Melbourne"],
    "Miami":          ["Miami Open"],
    "Indian Wells":   ["Indian Wells"],
    "Cincinnati":     ["Cincinnati", "Western Southern"],
    "Paris":          ["Paris Bercy", "Rolex Paris Masters"],
    "London":         ["ATP Finals", "Nitto ATP Finals"],
}

# Termos de superfície para quando não temos torneio específico
SURFACE_TERMS = {
    "clay":  ["clay court", "terre battue"],
    "grass": ["grass court", "Wimbledon", "Queens"],
    "hard":  ["hard court"],
}


def _get_season() -> str:
    m = date.today().month
    if m in (4, 5, 6):
        return "clay"
    if m in (6, 7):
        return "grass"
    return "hard"


def _build_queries(
    player_name: str,
    tournament_name: str | None,
    season: str,
    year: int,
) -> list[str]:
    """
    Gera queries em ordem de especificidade decrescente.
    Usa nome completo entre aspas (para jogadores menos famosos) + fallback só sobrenome.
    """
    last_name = player_name.split()[-1]
    queries = []

    # Tier 1: Nome completo + torneio específico (mais preciso)
    if tournament_name:
        terms = TOURNAMENT_TERMS.get(tournament_name, [tournament_name])
        queries.append(f'"{player_name}" tennis {terms[0]} {year}')
        queries.append(f'"{player_name}" {terms[0]} tennis')

    # Tier 2: Nome completo + superfície + ano
    surface_terms = SURFACE_TERMS.get(season, ["tennis"])
    queries.append(f'"{player_name}" tennis {surface_terms[0]} {year}')

    # Tier 3: Nome completo + tênis + ano (sem superfície — mais amplo)
    queries.append(f'"{player_name}" tennis {year}')

    # Tier 4: Só sobrenome + tênis (fallback para jogadores com nome longo/estrangeiro)
    if last_name.lower() != player_name.split()[0].lower():  # nome ≠ sobrenome
        queries.append(f'"{last_name}" tennis {year}')
        queries.append(f'"{last_name}" tennis')

    # Tier 5: Nome completo sem ano (último recurso)
    queries.append(f'"{player_name}" tennis')

    # Deduplicar mantendo ordem
    seen: set[str] = set()
    return [q for q in queries if not (q in seen or seen.add(q))]


def _name_ok(title: str, tags: str, player_name: str) -> bool:
    """Exige sobrenome (e primeiro nome se >= 5 chars) em título OU tags."""
    combined = (title + " " + tags).lower()
    parts = player_name.lower().split()
    last = parts[-1]
    if last not in combined:
        return False
    first = parts[0]
    if len(first) >= 5 and first not in combined:
        return False
    return True


def search_player_images(
    player_name: str,
    count: int = 6,
    season: str | None = None,
    tournament_name: str | None = None,
    exclude_urls: set | None = None,
) -> list[dict]:
    """
    Busca fotos CC do jogador no Flickr.
    Prioriza fotos do torneio atual → superfície → tênis genérico.
    Rejeita fotos onde o nome do jogador não aparece no título/tags.
    Ordena por data decrescente (mais recentes primeiro).
    """
    if not FLICKR_API_KEY:
        log.debug("FLICKR_API_KEY não configurado — Flickr desativado")
        return []

    season   = season or _get_season()
    year     = date.today().year
    exclude  = exclude_urls or set()
    results: list[dict] = []
    seen_ids: set[str]  = set()

    queries = _build_queries(player_name, tournament_name, season, year)

    for query in queries:
        if len(results) >= count:
            break

        params = {
            "method":         "flickr.photos.search",
            "api_key":        FLICKR_API_KEY,
            "text":           query,
            "license":        ",".join(ACCEPTED_LICENSES),
            "sort":           "date-posted-desc",   # mais recentes primeiro
            "content_type":   1,                    # só fotos
            "media":          "photos",
            "extras":         "url_b,url_c,url_z,license,owner_name,date_upload,title,tags",
            "per_page":       20,
            "format":         "json",
            "nojsoncallback": 1,
        }

        try:
            resp = requests.get(FLICKR_API, params=params, timeout=12)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log.warning(f"Flickr search falhou ({query!r}): {e}")
            continue

        photos = data.get("photos", {}).get("photo", [])
        log.debug(f"Flickr '{query}': {len(photos)} fotos brutas")

        for photo in photos:
            photo_id = str(photo.get("id", ""))
            if photo_id in seen_ids:
                continue

            # Pegar URL no maior tamanho disponível
            url = photo.get("url_b") or photo.get("url_c") or photo.get("url_z")
            if not url or url in exclude:
                continue

            title = photo.get("title", "")
            tags  = photo.get("tags", "")

            # Validação: nome do jogador deve estar no título ou nas tags
            if not _name_ok(title, tags, player_name):
                log.debug(f"Flickr rejeitou '{title}' para '{player_name}'")
                continue

            seen_ids.add(photo_id)
            license_id = str(photo.get("license", ""))

            results.append({
                "url":            url,
                "license":        LICENSE_NAMES.get(license_id, f"CC license {license_id}"),
                "author":         photo.get("ownername", "Flickr"),
                "source":         "flickr",
                "season_context": season,
                "tournament":     tournament_name or "",
                "title":          title,
            })

            if len(results) >= count:
                break

    if results:
        log.info(f"Flickr: {len(results)} fotos para '{player_name}' "
                 f"(torneio: {tournament_name or '—'}, season: {season})")
    else:
        log.info(f"Flickr: nenhuma foto encontrada para '{player_name}'")

    return results
