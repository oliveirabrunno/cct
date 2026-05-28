"""
Trend detector — identifica atletas em alta na mídia para gerar conteúdo.

Estratégia:
  - Top 30 ATP + Top 30 WTA carregados dinamicamente do ranking_cache
  - Lista de "em ascensão" hardcoded (Rafael Jódar, Mboko, etc.) — top 100 com hype
  - Brasileiros sempre prioridade máxima (Fonseca, Bia, Seyboth, Meligeni)
  - Threshold dinâmico baseado em ranking — top 10 dispara com 1 menção
  - Detector de BREAKING EVENTS — eliminação/lesão/retirada disparam imediatamente
"""

import json
import unicodedata
from pathlib import Path

from scrapers.google_news import fetch_recent_news
from scrapers.reddit_tennis import fetch_hot_posts
from utils.logger import get_logger

log = get_logger(__name__)

# Threshold de menções pra entrar em trend
TREND_THRESHOLD = 4
BRAZILIAN_THRESHOLD = 2

# Brasileiros — sempre prioridade
BRAZILIAN_PLAYERS = {
    "João Fonseca",
    "Beatriz Haddad Maia",
    "Beatriz Haddad",
    "Thiago Seyboth Wild",
    "Thiago Monteiro",
    "Felipe Meligeni",
    "Laura Pigossi",
}

# Atletas em ascensão / com buzz na mídia mesmo fora do top 30
RISING_STARS = {
    "Rafael Jódar",
    "Jakub Mensik",
    "Joel Schwarzler",
    "Learner Tien",
    "Federico Cinà",
    "Arthur Fils",
    "Luca Nardi",
    "Alexandra Eala",
    "Iva Jovic",
    "Tereza Valentova",
    "Mirra Andreeva",
    "Erika Andreeva",
    "Victoria Mboko",
}

# Lendas / nomes que SEMPRE rendem post quando há buzz
LEGENDS_ON_TOUR = {
    "Stan Wawrinka",
    "Andy Murray",
    "Gael Monfils",
    "Caroline Wozniacki",
    "Venus Williams",
}

# Termos que sinalizam BREAKING EVENT (alta prioridade independente de score)
BREAKING_KEYWORDS = [
    "eliminado", "eliminada", "elimina", "fora de", "eliminated", "knocked out",
    "lesão", "lesionado", "injury", "injured", "retira", "retirou", "withdraws",
    "withdraw", "walkover", "WO", "desiste", "abandona", "shock", "upset",
    "zebra", "surpresa", "stunning", "ousa", "derrota histórica", "first time loss",
]

# Termos POSITIVOS de breaking (vitórias importantes)
WIN_BREAKING_KEYWORDS = [
    "vence", "venceu", "derrotou", "elimina", "conquistou", "campeão",
    "campeona", "título", "title", "wins", "defeats", "champion", "lifts",
    "histórica", "primeira vitória", "first win",
]

RANKING_CACHE_DIR = Path("data")


def _normalize(text: str) -> str:
    """Remove acentos e normaliza para comparações."""
    if not text:
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFKD", text.lower())
        if not unicodedata.combining(c)
    ).strip()


def _generate_search_terms(name: str) -> list[str]:
    """
    Gera termos de busca a partir do nome do jogador:
      'João Fonseca' → ['joao fonseca', 'joão fonseca', 'fonseca']
      'Iga Świątek'  → ['iga swiatek', 'iga świątek', 'swiatek']
    """
    name_norm = _normalize(name)
    name_orig = name.lower()
    last_name = name_norm.split()[-1] if name_norm else ""
    terms = [name_norm, name_orig]
    if last_name and len(last_name) > 3:
        terms.append(last_name)
    # Remover duplicatas preservando ordem
    seen = set()
    return [t for t in terms if not (t in seen or seen.add(t))]


def _load_top_players_from_cache() -> dict[str, int]:
    """
    Carrega top 30 ATP + top 30 WTA do ranking_cache.
    Retorna dict {player_name: rank}.
    """
    players: dict[str, int] = {}
    for tour in ("atp", "wta"):
        path = RANKING_CACHE_DIR / f"ranking_cache_{tour}.json"
        if not path.exists():
            log.warning(f"Ranking cache não encontrado: {path}")
            continue
        try:
            data = json.loads(path.read_text())
            for p in data:
                name = p.get("name", "").strip()
                rank = p.get("rank", 999)
                if name and rank:
                    players[name] = rank
        except Exception as e:
            log.warning(f"Erro lendo {path}: {e}")
    log.info(f"Top players carregados: {len(players)} (ATP + WTA)")
    return players


def _build_monitored_players() -> dict[str, dict]:
    """
    Constrói dict completo de jogadores monitorados:
      {player_name: {"rank": int, "terms": list, "category": str}}
    Categorias: 'br' (brasileiro), 'top' (ranking), 'rising', 'legend'.
    """
    monitored: dict[str, dict] = {}
    top_players = _load_top_players_from_cache()

    # Brasileiros — prioridade máxima
    for name in BRAZILIAN_PLAYERS:
        monitored[name] = {
            "rank": top_players.get(name, 999),
            "terms": _generate_search_terms(name),
            "category": "br",
        }

    # Top 30 ATP + WTA do cache
    for name, rank in top_players.items():
        if name in monitored:
            continue
        monitored[name] = {
            "rank": rank,
            "terms": _generate_search_terms(name),
            "category": "top",
        }

    # Em ascensão (top 100 com buzz)
    for name in RISING_STARS:
        if name in monitored:
            continue
        monitored[name] = {
            "rank": top_players.get(name, 99),
            "terms": _generate_search_terms(name),
            "category": "rising",
        }

    # Lendas
    for name in LEGENDS_ON_TOUR:
        if name in monitored:
            continue
        monitored[name] = {
            "rank": top_players.get(name, 200),
            "terms": _generate_search_terms(name),
            "category": "legend",
        }

    return monitored


# Cache lazy — recarrega a cada chamada de check_all_players para pegar ranking atualizado
MONITORED_PLAYERS: dict[str, list[str]] = {}


def _refresh_monitored_legacy() -> None:
    """Atualiza dict MONITORED_PLAYERS no formato antigo (backward compat)."""
    global MONITORED_PLAYERS
    full = _build_monitored_players()
    MONITORED_PLAYERS = {name: data["terms"] for name, data in full.items()}


def _threshold_for(player_info: dict) -> int:
    """
    Threshold dinâmico:
      - Brasileiro: 1 (qualquer menção dispara)
      - Top 5: 1
      - Top 20: 2
      - Top 50: 3
      - Rising star: 2
      - Legend: 2
      - Outros: 4
    """
    cat = player_info["category"]
    rank = player_info["rank"]
    if cat == "br":
        return 1
    if cat == "rising" or cat == "legend":
        return 2
    if rank <= 5:
        return 1
    if rank <= 20:
        return 2
    if rank <= 50:
        return 3
    return TREND_THRESHOLD


def _detect_breaking_event(articles: list[dict], terms: list[str]) -> str | None:
    """
    Retorna o tipo de breaking event detectado nas notícias sobre o jogador.
    Tipos: 'elimination', 'injury', 'win', None.
    """
    for article in articles:
        text = (article.get("title_lower", "") + " " + article.get("summary_lower", ""))
        if not any(t in text for t in terms):
            continue
        for kw in BREAKING_KEYWORDS:
            if kw in text:
                if any(injury_kw in text for injury_kw in ["lesão", "injury", "lesionado"]):
                    return "injury"
                return "elimination"
        for kw in WIN_BREAKING_KEYWORDS:
            if kw in text:
                return "win"
    return None


class TrendDetector:

    async def check_all_players(self) -> list[dict]:
        _refresh_monitored_legacy()  # Mantém compatibilidade com código que importa MONITORED_PLAYERS

        recent_news = fetch_recent_news(hours=6)
        try:
            reddit_posts = fetch_hot_posts(min_score=500, max_age_hours=12)
        except Exception as e:
            log.debug(f"Reddit indisponível: {e}")
            reddit_posts = []

        full_monitored = _build_monitored_players()
        trending: list[dict] = []

        for player_name, info in full_monitored.items():
            score = 0
            signals: dict = {"category": info["category"], "rank": info["rank"]}

            news_count = self._count_news_mentions(recent_news, info["terms"])
            news_score = min(news_count, 5)
            score += news_score
            signals["news_count"] = news_count

            reddit_hit = self._check_reddit_mentions(reddit_posts, info["terms"])
            if reddit_hit:
                score += 3
                signals["reddit_post"] = reddit_hit

            # Detectar breaking events — bypass threshold
            breaking = _detect_breaking_event(recent_news, info["terms"])
            if breaking:
                signals["breaking"] = breaking
                # Eliminação/injury/win de top 30 → forçar entrada na lista
                if info["rank"] <= 30 or info["category"] in {"br", "rising"}:
                    score = max(score, 10)  # Score artificial alto = entra com prioridade
                    log.info(f"BREAKING [{breaking}]: {player_name} (rank {info['rank']})")

            threshold = _threshold_for(info)
            if score >= threshold:
                trending.append({
                    "player": player_name,
                    "score": score,
                    "threshold": threshold,
                    "signals": signals,
                    "category": info["category"],
                    "rank": info["rank"],
                    "news": [
                        a for a in recent_news
                        if any(t in a["title_lower"] for t in info["terms"])
                    ][:3],
                })
                log.info(
                    f"TREND: {player_name} [{info['category']} #{info['rank']}] "
                    f"score={score} threshold={threshold} signals={signals}"
                )

        # Ordenar: breaking events primeiro, depois por score, depois por rank
        trending.sort(key=lambda x: (
            0 if x["signals"].get("breaking") else 1,
            -x["score"],
            x["rank"],
        ))
        return trending

    def _count_news_mentions(self, articles: list, terms: list) -> int:
        count = 0
        for article in articles:
            text = article["title_lower"] + " " + article.get("summary_lower", "")
            if any(t in text for t in terms):
                count += 1
        return count

    def _check_reddit_mentions(self, posts: list, terms: list) -> dict | None:
        for post in posts:
            if any(t in post["title_lower"] for t in terms):
                return post
        return None


# Inicialização eager pra módulos que importam MONITORED_PLAYERS no top-level
try:
    _refresh_monitored_legacy()
except Exception as e:
    log.warning(f"Falha na inicialização eager de MONITORED_PLAYERS: {e}")
    MONITORED_PLAYERS = {"João Fonseca": ["joao fonseca", "fonseca"]}  # fallback mínimo
