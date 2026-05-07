"""
Enriquece resultados de partidas com stats contextuais.
Detecta upsets, H2H, última vitória no nível, etc.
Alimenta o gerador de cards de resultado.
"""

import re
from datetime import datetime
from utils.logger import get_logger

log = get_logger(__name__)


def get_player_ranking(name: str) -> dict | None:
    """Retorna ranking ao vivo do jogador (ATP ou WTA)."""
    try:
        from scrapers.live_ranking import fetch_atp_live_rankings, fetch_wta_live_rankings
        for fetch, tour in [(fetch_atp_live_rankings, "atp"), (fetch_wta_live_rankings, "wta")]:
            players = fetch(100)
            name_lower = name.lower()
            for p in players:
                if any(part in p["name"].lower() for part in name_lower.split() if len(part) > 3):
                    return {**p, "tour": tour}
    except Exception as e:
        log.warning(f"Ranking lookup falhou para {name}: {e}")
    return None


def detect_upset(winner: str, loser: str) -> dict:
    """
    Detecta se é um upset e calcula a magnitude.
    Retorna: {"is_upset": bool, "ranking_diff": int, "winner_rank": int, "loser_rank": int}
    """
    winner_data = get_player_ranking(winner)
    loser_data  = get_player_ranking(loser)

    winner_rank = winner_data["rank"] if winner_data else 999
    loser_rank  = loser_data["rank"]  if loser_data  else 999

    # Upset: vencedor pior ranqueado que o perdedor
    ranking_diff = winner_rank - loser_rank
    is_upset = ranking_diff > 10  # diferença mínima para considerar upset significativo

    return {
        "is_upset":     is_upset,
        "ranking_diff": ranking_diff,
        "winner_rank":  winner_rank,
        "loser_rank":   loser_rank,
        "winner_data":  winner_data,
        "loser_data":   loser_data,
    }


def parse_score_sets(score_str: str) -> list[tuple[int, int]]:
    """Converte '6-3 6-2' em [(6,3),(6,2)]."""
    sets = []
    for part in score_str.split():
        m = re.match(r"(\d+)-(\d+)", part)
        if m:
            sets.append((int(m.group(1)), int(m.group(2))))
    return sets


def score_dominance(score_str: str) -> str:
    """Retorna adjetivo descritivo da dominância: 'dominante', 'disputado', 'virada'."""
    sets = parse_score_sets(score_str)
    if not sets:
        return ""

    # Verificar se houve break de sets (perdeu o 1º e venceu os outros)
    if len(sets) == 3 and sets[0][0] < sets[0][1]:
        return "virada"

    total_games_won  = sum(s[0] for s in sets)
    total_games_lost = sum(s[1] for s in sets)

    if total_games_won - total_games_lost >= 6:
        return "dominante"
    elif total_games_won - total_games_lost <= 2:
        return "disputado"
    return "convincente"


def search_player_recent_context(player_name: str, tournament: str) -> str:
    """
    Busca no Google News contexto recente do jogador.
    Retorna string com stat mais relevante encontrado.
    """
    try:
        from scrapers.google_news import search_news
        articles = search_news(f"{player_name} tennis {tournament}", hours=72)
        if not articles:
            articles = search_news(player_name, hours=168)  # última semana

        if articles:
            return articles[0].get("title", "")
    except Exception:
        pass
    return ""


def build_match_context(winner: str, loser: str, score: str, tournament: str, round_name: str = "") -> dict:
    """
    Monta o contexto completo de uma partida para o gerador de card.
    """
    upset_data = detect_upset(winner, loser)
    dominance  = score_dominance(score)
    sets       = parse_score_sets(score)

    # Label principal baseado no contexto
    if upset_data["is_upset"] and upset_data["ranking_diff"] > 30:
        label = "VIRADA DO DIA"
    elif upset_data["is_upset"]:
        label = "SURPRESA"
    elif dominance == "virada":
        label = "VIRADA"
    elif dominance == "dominante":
        label = "RESULTADO"
    else:
        label = "RESULTADO"

    # Score formatado set a set
    score_formatted = "  ".join(f"{a}-{b}" for a, b in sets) if sets else score

    # Buscar contexto de notícias
    news_context = search_player_recent_context(winner, tournament)

    return {
        "winner":          winner,
        "loser":           loser,
        "score":           score,
        "score_formatted": score_formatted,
        "sets":            sets,
        "tournament":      tournament,
        "round":           round_name,
        "label":           label,
        "dominance":       dominance,
        "is_upset":        upset_data["is_upset"],
        "ranking_diff":    upset_data["ranking_diff"],
        "winner_rank":     upset_data["winner_rank"],
        "loser_rank":      upset_data["loser_rank"],
        "news_context":    news_context,
        "timestamp":       datetime.now().isoformat(),
    }
