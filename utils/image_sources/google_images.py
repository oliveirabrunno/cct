"""
Google Images via SerpAPI com fallback para DuckDuckGo Images.

SerpAPI requer SERPAPI_KEY no .env (plano gratuito: 100 buscas/mês).
Quando SerpAPI esgota créditos ou a key está ausente, DuckDuckGo é usado
automaticamente — sem API key, sem limite de créditos.

Regras absolutas de segurança (após incidente de banimento por NSFW em 2026-05-20):
  - DDG SEMPRE com safesearch='on' (NUNCA off/moderate).
  - Toda query DEVE conter "tennis" — se não tiver, é rejeitada.
  - Domínios NSFW conhecidos bloqueados na fonte.
  - Sobrenome do jogador deve aparecer no host/título quando disponível.

Busca "{player} tennis clay {year}" para fotos da temporada atual.
"""

import os
import re
import requests
from datetime import date
from urllib.parse import urlparse
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

# Domínios bloqueados (NSFW, irrelevantes, agregadores de baixa qualidade)
BLOCKED_DOMAINS = {
    "pornhub.com", "xvideos.com", "xhamster.com", "redtube.com",
    "youporn.com", "tube8.com", "spankbang.com", "xnxx.com",
    "onlyfans.com", "fansly.com", "stripchat.com",
    "tnaflix.com", "drtuber.com", "porn.com", "porntrex.com",
    "eporner.com", "txxx.com", "hclips.com", "fapality.com",
    "manyvids.com", "chaturbate.com", "myfreecams.com",
    # Imagens irrelevantes (alimentos, produtos, etc — já causaram bug do "rice bag")
    "alibaba.com", "aliexpress.com", "amazon.com", "ebay.com",
    "etsy.com", "shutterstock.com",  # marca d'água gigante
}

# Domínios confiáveis de tênis — imagens desses sites passam sem validação extra
# (já são garantidamente sobre tênis)
TRUSTED_DOMAINS = {
    # Circuitos oficiais
    "atptour.com", "wtatennis.com",
    # Grand Slams
    "rolandgarros.com", "wimbledon.com", "ausopen.com", "usopen.org",
    # Mídia esportiva de tênis
    "tennismajors.com", "tennishead.net", "tennis.com",
    "essentiallysports.com", "tennisworldusa.org", "tennisabstract.com",
    "tennistonic.com", "tennisuptodate.com", "tennisnow.com",
    # Agências de foto / imagem editorial
    "gettyimages.com", "imago-images.com",
    "reuters.com", "ap.org",
    # Wikimedia / Flickr (já validados por _name_ok / _name_in_url)
    "wikimedia.org", "wikipedia.org",
    "flickr.com", "staticflickr.com",
    # Mídia esportiva geral que cobre tênis com fotos reais
    "eurosport.com", "skysports.com", "bbc.co.uk", "espn.com",
    "sportal.com.au", "marca.com", "lequipe.fr",
}

# Palavras que NUNCA podem aparecer na URL/título (defesa em profundidade)
BLOCKED_KEYWORDS = {
    "porn", "xxx", "nude", "naked", "nsfw", "adult", "erotic",
    "sex", "fuck", "boob", "tits", "ass", "anal",
    "rice", "grain", "bag of",  # bug do "saco de arroz"
    "recipe", "cooking", "food",
    # Paisagens / natureza — incidente de paisagem publicada em 2026-05-20
    "landscape", "mountain", "sunset", "sunrise", "beach", "ocean",
    "forest", "nature", "skyline", "scenery", "panorama",
    "aerial", "drone", "cityscape", "architecture", "wallpaper",
    "waterfall", "desert", "glacier", "volcano", "canyon",
}

# Keywords de tênis usadas para validar relevância de imagem
_TENNIS_KEYWORDS = {
    "tennis", "tenis", "tenista", "atp", "wta",
    "slam", "open", "masters",
    "roland garros", "wimbledon", "us open", "australian open",
    "roland-garros", "french open",
    "racket", "raquete", "raqueta",
    "court", "quadra", "saibro", "clay", "grass", "hard court",
    "forehand", "backhand", "serve", "volley", "ace",
    "semifinal", "quarterfinal", "final",
    "match", "set", "game", "tiebreak",
    # Nomes de torneios conhecidos
    "roma", "madrid", "monte carlo", "monte-carlo", "indian wells",
    "miami", "cincinnati", "shanghai", "paris", "turin",
    "barcelona", "hamburg", "halle", "queens", "eastbourne",
}


def _is_safe_image(url: str, title: str = "", source: str = "") -> bool:
    """Retorna False se a imagem deve ser rejeitada (NSFW/irrelevante)."""
    if not url:
        return False

    try:
        host = urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        host = ""

    # Bloqueia domínio inteiro
    for blocked in BLOCKED_DOMAINS:
        if blocked in host:
            log.warning(f"Imagem REJEITADA por domínio bloqueado: {host}")
            return False

    # Verifica keywords na URL, título e source
    combined = f"{url} {title} {source}".lower()
    for kw in BLOCKED_KEYWORDS:
        # Word boundary para evitar match em "essex", "passport", etc
        if re.search(rf"\b{re.escape(kw)}\b", combined):
            log.warning(f"Imagem REJEITADA por keyword '{kw}': {url[:80]}")
            return False

    return True


def _is_tennis_relevant(url: str, title: str, source: str, player_name: str) -> bool:
    """Valida que a imagem é de fato sobre tênis.

    Regras:
    1. Se o domínio está em TRUSTED_DOMAINS → aceita (já é fonte de tênis).
    2. Caso contrário, exige:
       a) Pelo menos 1 keyword de tênis no título/source.
       b) O sobrenome do jogador no título/source.
    3. Se nenhuma dessas condições for atendida → rejeita.

    Adicionado após incidente de paisagem publicada em 2026-05-20.
    """
    if not url:
        return False

    try:
        host = urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        host = ""

    # Domínio confiável → aceita sem verificação adicional
    for trusted in TRUSTED_DOMAINS:
        if trusted in host:
            return True

    combined = f"{title} {source}".lower()

    # Exigir keyword de tênis no título/source
    has_tennis_context = any(kw in combined for kw in _TENNIS_KEYWORDS)
    if not has_tennis_context:
        log.info(f"Imagem REJEITADA: sem contexto de tênis no título/source: {title[:60]!r} ({host})")
        return False

    # Exigir sobrenome do jogador no título/source
    if player_name:
        parts = player_name.lower().split()
        last_name = parts[-1] if parts else ""
        if last_name and len(last_name) >= 3:
            # Usa regex word boundary para match exato
            if not re.search(rf"\b{re.escape(last_name)}\b", combined):
                log.info(
                    f"Imagem REJEITADA: sobrenome '{last_name}' ausente em título/source: "
                    f"{title[:60]!r} ({host})"
                )
                return False

    return True


def _query_has_tennis_context(query: str) -> bool:
    """Verifica se a query tem contexto de tênis (defesa contra queries vazias/genéricas)."""
    q = query.lower()
    return any(kw in q for kw in ("tennis", "tenista", "atp", "wta", "tenis"))


def _get_season() -> str:
    month = date.today().month
    if month in (4, 5, 6):
        return "clay"
    if month in (6, 7):
        return "grass"
    return "hard"


def _build_queries(player_name: str, year: int, tournament_name: str = None, search_override: str = None) -> list[str]:
    if search_override:
        # Defesa: nunca confiar em override sem "tennis"
        if not _query_has_tennis_context(search_override):
            search_override = f"{search_override} tennis"
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
    """DuckDuckGo Images — fallback gratuito, com safesearch='on' obrigatório."""
    try:
        from ddgs import DDGS
    except ImportError:
        log.debug("ddgs não instalado — DDG pulado (pip install ddgs)")
        return []

    for query in queries:
        # Guard: nunca buscar sem contexto de tênis
        if not _query_has_tennis_context(query):
            log.warning(f"DDG pulou query sem contexto de tênis: {query!r}")
            continue

        try:
            results = []
            with DDGS() as ddgs:
                # safesearch='on' é OBRIGATÓRIO — incidente de NSFW em 2026-05-20
                # Extrair sobrenome do jogador da query para validação de relevância
                _player_from_query = query.split(" tennis")[0].strip().strip('"') if " tennis" in query.lower() else ""
                for img in ddgs.images(query, max_results=count * 4, safesearch="on"):
                    url    = img.get("image") or ""
                    title  = img.get("title", "")
                    source = img.get("source", "DuckDuckGo")
                    w = int(img.get("width", 0) or 0)
                    h = int(img.get("height", 0) or 0)

                    if w < 600 or h < 600:
                        continue
                    # Rejeitar aspect ratios extremos (banners, faixas, panorâmicas)
                    ratio = max(w, h) / max(1, min(w, h))
                    if ratio > 2.2:
                        continue
                    if not _is_safe_image(url, title, source):
                        continue
                    # Validar relevância: deve ser sobre tênis + conter nome do jogador
                    if not _is_tennis_relevant(url, title, source, _player_from_query):
                        continue

                    results.append({
                        "url":     url,
                        "width":   w,
                        "height":  h,
                        "license": "unknown",
                        "author":  source,
                        "source":  "duckduckgo",
                    })
                    if len(results) >= count:
                        break
            if results:
                log.info(f"DuckDuckGo Images: '{query}' → {len(results)} fotos (safesearch=on)")
                return results
        except Exception as e:
            log.warning(f"DuckDuckGo Images falhou ({query!r}): {e}")

    return []


def _serpapi_search(query: str, num: int = 10) -> list[dict]:
    """Uma busca no SerpAPI. Retorna lista de imagens ou [] em erro/quota."""
    # Guard: nunca buscar sem contexto de tênis
    if not _query_has_tennis_context(query):
        log.warning(f"SerpAPI pulou query sem contexto de tênis: {query!r}")
        return []

    params = {
        "q":       query,
        "tbm":     "isch",
        "api_key": SERPAPI_KEY,
        "num":     num,
        "safe":    "active",  # safesearch obrigatório
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


def _serpapi_to_result(img: dict, player_name: str = "") -> dict | None:
    """Converte resultado bruto do SerpAPI em dict normalizado, aplicando filtros."""
    w = img.get("original_width", 0)
    h = img.get("original_height", 0)
    if w < 600 or h < 600:
        return None
    ratio = max(w, h) / max(1, min(w, h))
    if ratio > 2.2:
        return None

    url    = img.get("original") or ""
    title  = img.get("title", "")
    source = img.get("source", "Google CC")
    if not _is_safe_image(url, title, source):
        return None
    # Validar relevância: deve ser sobre tênis + conter nome do jogador
    if not _is_tennis_relevant(url, title, source, player_name):
        return None

    return {
        "url":    url,
        "width":  w,
        "height": h,
        "license": "CC",
        "author":  source,
        "source":  "google_cc",
    }


def search_cc_player_photo(player_name: str, year: int = None, tournament_name: str = None) -> dict | None:
    """Busca uma foto do jogador. Tenta SerpAPI primeiro, cai para DuckDuckGo."""
    target_year = year or CURRENT_YEAR
    queries = _build_queries(player_name, target_year, tournament_name)

    # Tenta SerpAPI
    if SERPAPI_KEY:
        for query in queries:
            for img in _serpapi_search(query, num=5):
                result = _serpapi_to_result(img, player_name=player_name)
                if result:
                    log.info(f"Google Images (SerpAPI): '{player_name}' — {query!r}")
                    return result

    # Fallback: DuckDuckGo
    results = _ddg_search_images(queries, count=1)
    if results:
        log.info(f"DuckDuckGo Images (fallback): '{player_name}'")
        return results[0]

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
            result = _serpapi_to_result(img, player_name=player_name)
            if result:
                results.append(result)
            if len(results) >= count:
                break
        if results:
            return results
        log.info(f"SerpAPI sem resultados para '{player_name}' — tentando DuckDuckGo")

    # Fallback: DuckDuckGo
    return _ddg_search_images(queries, count=count)
