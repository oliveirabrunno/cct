"""
Calendário preditivo de partidas para o pattern event-driven burst.

Mantém data/upcoming_matches.json com lista de jogos importantes nas próximas 72h,
cada um com importance score e timestamp. O burst_orchestrator usa esse arquivo
para disparar conteúdo (preview, countdown, live, post-match) no horário certo.

Fonte: Flashscore (página do torneio atual) + entries do CURRENT_TOURNAMENT.
"""

import asyncio
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from utils.logger import get_logger

log = get_logger(__name__)

CALENDAR_FILE = Path("data/upcoming_matches.json")
CALENDAR_FILE.parent.mkdir(parents=True, exist_ok=True)

# Jogadores brasileiros têm prioridade máxima
BRAZILIAN_PLAYERS = {"fonseca", "haddad", "meligeni", "seyboth", "wild", "monteiro"}

# Top players por importância de matchup
TOP_TIER = {"sinner", "alcaraz", "djokovic", "swiatek", "sabalenka", "gauff"}
TIER_2 = {"zverev", "medvedev", "rublev", "fritz", "shelton", "ruud", "rybakina",
          "pegula", "anisimova", "keys", "paolini", "andreeva"}


def _name_lower(name: str) -> str:
    return name.lower().strip()


def _has_player(name: str, group: set[str]) -> bool:
    n = _name_lower(name)
    return any(p in n for p in group)


def compute_importance(player_a: str, player_b: str, tournament: str, round_name: str = "") -> int:
    """
    Score 1-10. 10 = burst máximo (Grand Slam + brasileiro), 1 = ignorar.
    """
    tour_lower = tournament.lower()
    round_lower = round_name.lower()
    score = 3  # baseline

    # Grand Slam = +3
    if any(gs in tour_lower for gs in ["roland garros", "french open", "wimbledon",
                                        "us open", "australian open"]):
        score += 3
    # Masters 1000 = +2
    elif "masters 1000" in tour_lower or "1000" in tour_lower:
        score += 2

    # Brasileiro jogando = +4 (categoria prioridade nacional)
    if _has_player(player_a, BRAZILIAN_PLAYERS) or _has_player(player_b, BRAZILIAN_PLAYERS):
        score += 4

    # Top tier vs top tier = +2
    a_top = _has_player(player_a, TOP_TIER)
    b_top = _has_player(player_b, TOP_TIER)
    if a_top and b_top:
        score += 2
    elif a_top or b_top:
        score += 1

    # Rodada eliminatória avançada = +1
    if any(r in round_lower for r in ["final", "semi", "quartas", "quarter", "1/4", "1/2"]):
        score += 1

    return min(score, 10)


def burst_plan(importance: int) -> list[dict]:
    """
    Retorna a lista de triggers (offset em horas + tipo de post) para a partida,
    proporcional à importância.
    """
    if importance >= 9:  # Grand Slam + brasileiro/top tier
        return [
            {"offset_h": -48, "type": "preview_carousel",  "label": "T-48h preview"},
            {"offset_h": -24, "type": "stat_card",         "label": "T-24h stat"},
            {"offset_h": -12, "type": "poll_story",        "label": "T-12h poll"},
            {"offset_h":  -2, "type": "countdown_story",   "label": "T-2h countdown"},
            {"offset_h":  +1, "type": "result_card",       "label": "T+1h result (se vencer)"},
            {"offset_h":  +3, "type": "highlights_carousel","label": "T+3h highlights"},
        ]
    elif importance >= 7:
        return [
            {"offset_h": -24, "type": "preview_carousel",  "label": "T-24h preview"},
            {"offset_h":  -6, "type": "poll_story",        "label": "T-6h poll"},
            {"offset_h":  +1, "type": "result_card",       "label": "T+1h result"},
            {"offset_h":  +3, "type": "highlights_carousel","label": "T+3h highlights"},
        ]
    elif importance >= 5:
        return [
            {"offset_h":  -6, "type": "stat_card",         "label": "T-6h stat"},
            {"offset_h":  +2, "type": "result_card",       "label": "T+2h result"},
        ]
    else:
        return []


def _parse_match_time(start_ts: str | int | None, date_text: str = "") -> datetime | None:
    if start_ts:
        try:
            return datetime.fromtimestamp(int(start_ts), tz=timezone.utc)
        except (ValueError, TypeError):
            pass
    # Fallback heurístico: assume hoje + parse "HH:MM" no date_text
    if date_text:
        m = re.search(r"(\d{1,2}):(\d{2})", date_text)
        if m:
            today = datetime.now(timezone.utc).date()
            return datetime(today.year, today.month, today.day,
                            int(m.group(1)), int(m.group(2)), tzinfo=timezone.utc)
    return None


async def fetch_upcoming_matches(hours_ahead: int = 72) -> list[dict]:
    """
    Busca partidas agendadas (status='scheduled' ou similar) nas próximas hours_ahead horas.
    Usa flashscore.fetch_live_scores (que agora varre URLs de Grand Slam).
    """
    from scrapers.flashscore import fetch_live_scores

    raw_matches = await fetch_live_scores()
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(hours=hours_ahead)
    upcoming: list[dict] = []

    for m in raw_matches:
        status = m.get("status", "").lower()
        # Partidas agendadas têm status vazio ou "scheduled"/"00:00 ip" etc.
        # Finalizadas têm "finished", "fim", "final"
        is_finished = any(s in status for s in ["finished", "fim", "final", "retired", "walkover"])
        is_live = any(s in status for s in ["set", "ip", "live"])
        if is_finished or is_live:
            continue

        match_time = _parse_match_time(m.get("start_ts"), m.get("date_text", ""))
        if not match_time:
            continue
        if match_time < now or match_time > cutoff:
            continue

        player_a = m.get("player_a", "")
        player_b = m.get("player_b", "")
        tournament = m.get("tournament", "")
        importance = compute_importance(player_a, player_b, tournament)

        if importance < 5:  # filtrar jogos pouco relevantes
            continue

        plan = burst_plan(importance)
        upcoming.append({
            "player_a": player_a,
            "player_b": player_b,
            "tournament": tournament,
            "match_time_utc": match_time.isoformat(),
            "match_time_brt": (match_time - timedelta(hours=3)).isoformat(),
            "importance": importance,
            "burst_plan": plan,
            "match_key": f"{_name_lower(player_a)}_vs_{_name_lower(player_b)}_{match_time.date().isoformat()}",
        })

    upcoming.sort(key=lambda x: (-x["importance"], x["match_time_utc"]))
    return upcoming


def save_calendar(matches: list[dict]) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "matches": matches,
    }
    CALENDAR_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    log.info(f"Calendário salvo: {len(matches)} partidas em {CALENDAR_FILE}")


def load_calendar() -> list[dict]:
    if not CALENDAR_FILE.exists():
        return []
    try:
        data = json.loads(CALENDAR_FILE.read_text())
        return data.get("matches", [])
    except Exception as e:
        log.warning(f"Falha ao ler {CALENDAR_FILE}: {e}")
        return []


async def update_calendar() -> list[dict]:
    """Chama fetch_upcoming_matches, salva no JSON e retorna a lista."""
    log.info("Atualizando calendário de jogos...")
    matches = await fetch_upcoming_matches(hours_ahead=72)
    save_calendar(matches)
    if matches:
        log.info(f"Próximos jogos importantes:")
        for m in matches[:5]:
            log.info(f"  [{m['importance']}] {m['player_a']} vs {m['player_b']} — "
                     f"{m['match_time_brt'][:16]} ({m['tournament']})")
    else:
        log.info("Nenhum jogo importante nas próximas 72h")
    return matches


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(update_calendar())
