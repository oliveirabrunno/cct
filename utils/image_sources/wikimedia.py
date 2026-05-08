"""
Wikimedia Commons — busca com intitle: para garantir nome do jogador no arquivo.
Prioriza temporada atual (clay/grass/hard) por ordem de queries.
"""

import re
import requests
from datetime import date
from utils.logger import get_logger

log = get_logger(__name__)

WIKIMEDIA_API = "https://commons.wikimedia.org/w/api.php"
ACCEPTED_LICENSES = ["CC", "Public Domain", "cc", "pd"]
HEADERS = {
    "User-Agent": "CafeComTenis/1.0 (https://instagram.com/cafecomteniss; cafecomtenis@gmail.com)"
}

CURRENT_YEAR = date.today().year
PREV_YEAR    = CURRENT_YEAR - 1

# Termos por temporada — usados na busca intitle + keyword
SEASON_TERMS = {
    "clay":  ["Roland Garros", "clay", "Roma", "Madrid"],
    "grass": ["Wimbledon", "grass", "Queens"],
    "hard":  ["US Open", "Australian Open", "hard court"],
}

# Palavras no filename que indicam temporada ERRADA — descartar
SEASON_BAD_KEYWORDS = {
    "clay":  ["US_Open", "USOpen", "Australian_Open", "AustralianOpen",
              "Wimbledon", "Queens", "Basel", "Miami", "Indian_Wells"],
    "grass": ["US_Open", "Australian_Open", "Roland_Garros", "clay"],
    "hard":  ["Roland_Garros", "Wimbledon"],
}


def get_season_context() -> str:
    m = date.today().month
    if m in (4, 5, 6):
        return "clay"
    if m in (6, 7):
        return "grass"
    return "hard"


def _filename_ok(url: str, season: str) -> bool:
    bad = SEASON_BAD_KEYWORDS.get(season, [])
    fname = url.split("/")[-1]
    return not any(kw.lower() in fname.lower() for kw in bad)


def _run_query(query: str, max_results: int, seen_urls: set, season: str) -> list[dict]:
    """Executa uma query no Wikimedia e filtra por licença + temporada."""
    params = {
        "action":       "query",
        "generator":    "search",
        "gsrnamespace": 6,
        "gsrsearch":    query,
        "gsrlimit":     max_results,
        "prop":         "imageinfo",
        "iiprop":       "url|size|mime|extmetadata",
        "iiurlwidth":   960,
        "format":       "json",
    }
    try:
        resp = requests.get(WIKIMEDIA_API, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.debug(f"Wikimedia query falhou ({query!r}): {e}")
        return []

    results = []
    for page in data.get("query", {}).get("pages", {}).values():
        info = page.get("imageinfo", [{}])[0]
        meta = info.get("extmetadata", {})

        if not info.get("mime", "").startswith("image/"):
            continue

        license_short = meta.get("LicenseShortName", {}).get("value", "")
        if not any(ok in license_short for ok in ACCEPTED_LICENSES):
            continue

        url = info.get("thumburl") or info.get("url", "")
        if not url or url in seen_urls:
            continue

        if not _filename_ok(url, season):
            continue

        seen_urls.add(url)
        author_raw = meta.get("Artist", {}).get("value", "Unknown")
        author = re.sub(r"<[^>]+>", "", author_raw).strip()

        results.append({
            "url":            url,
            "width":          info.get("thumbwidth")  or info.get("width", 0),
            "height":         info.get("thumbheight") or info.get("height", 0),
            "license":        license_short,
            "author":         author,
            "source":         "wikimedia",
            "season_context": season,
        })

    return results


def _ascii(s: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").lower()


def _name_in_url(url: str, player_name: str) -> bool:
    """Verifica se alguma parte relevante do nome do jogador está na URL do arquivo.
    Normaliza diacríticos (ex: Świątek → swiatek) para comparar com URLs ASCII."""
    url_ascii = _ascii(url)
    parts = [_ascii(p) for p in player_name.split() if len(p) > 2]
    return any(p in url_ascii for p in parts)


def search_player_images(
    player_name: str,
    max_results: int = 10,
    season_context: str | None = None,
) -> list[dict]:
    """
    Busca fotos do jogador no Wikimedia Commons.
    Usa nome completo + 'tennis' em todas as queries para evitar ambiguidade
    (ex: não pegar imagem de helicóptero Haddad ou atleta Fonseca de outra modalidade).
    """
    season     = season_context or get_season_context()
    last_name  = player_name.split()[-1]
    seen_urls: set[str] = set()
    results:   list[dict] = []

    clay_terms = SEASON_TERMS.get(season, ["tennis"])
    queries = [
        # 1. Nome completo + tennis + temporada + ano (mais preciso)
        f'"{player_name}" tennis {clay_terms[0]} {CURRENT_YEAR}',
        f'"{player_name}" tennis {clay_terms[0]} {PREV_YEAR}',
        # 2. Nome completo + tennis (qualquer temporada)
        f'"{player_name}" tennis',
        # 3. intitle com sobrenome + tennis (fallback — sempre inclui tennis)
        f'intitle:"{last_name}" tennis {clay_terms[0]}',
        f'intitle:"{last_name}" tennis',
    ]

    for query in queries:
        if len(results) >= max_results:
            break
        batch = _run_query(query, max_results=6, seen_urls=seen_urls, season=season)
        results.extend(batch)

    # Filtrar resultados onde o nome do jogador NÃO aparece na URL do arquivo
    validated = [r for r in results if _name_in_url(r["url"], player_name)]
    final = validated if validated else results  # fallback sem filtro se não sobrar nada

    log.info(f"Wikimedia: {len(final)} fotos para '{player_name}' (temporada: {season})")
    return final[:max_results]


def get_player_photos(
    player_name: str,
    count: int = 6,
    exclude_urls: set | None = None,
) -> list[dict]:
    exclude   = exclude_urls or set()
    all_photos = search_player_images(player_name, max_results=max(count * 3, 12))
    available  = [p for p in all_photos if p["url"] not in exclude]

    portraits  = [p for p in available if p.get("height", 0) >= p.get("width", 1)]
    landscapes = [p for p in available if p.get("width",  1)  > p.get("height", 0)]

    result: list[dict] = []
    pi = li = 0
    while len(result) < count:
        added = False
        if pi < len(portraits):
            result.append(portraits[pi]); pi += 1; added = True
        if len(result) < count and li < len(landscapes):
            result.append(landscapes[li]); li += 1; added = True
        if not added:
            break

    return result[:count]


def get_best_player_photo(player_name: str, preferred_type: str = "any") -> dict | None:
    photos = get_player_photos(player_name, count=4)
    if not photos:
        return None

    portraits  = [p for p in photos if p.get("height", 0) >= p.get("width", 1)]
    landscapes = [p for p in photos if p.get("width",  1)  > p.get("height", 0)]

    if preferred_type == "headshot":
        return portraits[0] if portraits else photos[0]
    elif preferred_type == "action":
        return landscapes[0] if landscapes else (portraits[1] if len(portraits) > 1 else photos[-1])
    return portraits[0] if portraits else photos[0]
