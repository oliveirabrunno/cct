"""
Scout pós-jogo: extrai estatísticas detalhadas de partidas finalizadas.

Fontes (em ordem de prioridade):
  1. Sackmann CSV — stats de saque/devolução da última partida do jogador
  2. Flashscore (Playwright) — lista de partidas finalizadas hoje
  
O Flashscore serve para descobrir QUEM jogou; o Sackmann entrega as STATS.
"""

import asyncio
from datetime import date
from pathlib import Path
from utils.logger import get_logger

log = get_logger(__name__)

FLASHSCORE_URL = "https://www.flashscore.com"
SACKMANN_DIR   = Path("data/sackmann/tennis_atp")
CURRENT_YEAR   = date.today().year


# ─── Encontrar partidas finalizadas ───────────────────────────────────────────

async def find_recent_finished_matches(monitored_players: list[str] = None) -> list[dict]:
    """
    Lista partidas finalizadas recentes no Flashscore (só para descobrir quem jogou).
    """
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

            await page.goto(f"{FLASHSCORE_URL}/tennis/", timeout=30000, wait_until="domcontentloaded")
            await page.wait_for_timeout(4000)

            matches = await page.evaluate("""() => {
                const rows = document.querySelectorAll("[class*='event__match']");
                const finished = [];
                rows.forEach(row => {
                    const status = row.querySelector("[class*='event__stage']");
                    if (!status) return;
                    const st = status.textContent.trim().toLowerCase();
                    if (!['finished','fim','fin','ended','final'].some(s => st.includes(s))) return;

                    const id   = row.getAttribute('id') || '';
                    const home = row.querySelector("[class*='event__participant--home']");
                    const away = row.querySelector("[class*='event__participant--away']");
                    const sh   = row.querySelector("[class*='event__score--home']");
                    const sa   = row.querySelector("[class*='event__score--away']");
                    const tourn = document.querySelector("[class*='event__title']");

                    if (home && away) {
                        finished.push({
                            id:         id,
                            player_a:   home.textContent.trim(),
                            player_b:   away.textContent.trim(),
                            score_a:    sh ? sh.textContent.trim() : '',
                            score_b:    sa ? sa.textContent.trim() : '',
                            tournament: tourn ? tourn.textContent.trim() : ''
                        });
                    }
                });
                return finished;
            }""")

            await browser.close()

        if monitored_players:
            lower = [p.lower() for p in monitored_players]
            matches = [
                m for m in matches
                if any(
                    any(part in m["player_a"].lower() or part in m["player_b"].lower()
                        for part in p.split() if len(part) > 3)
                    for p in lower
                )
            ]

        log.info(f"Flashscore: {len(matches)} partidas finalizadas de jogadores monitorados")
        return matches

    except Exception as e:
        log.error(f"Erro ao buscar partidas: {e}")
        return []


# ─── Stats da última partida via Sackmann ─────────────────────────────────────

def get_last_match_stats(player_name: str, surface: str = None, year: int = None) -> dict:
    """
    Busca as stats da ÚLTIMA partida do jogador nos CSVs do Sackmann.
    Retorna stats de saque e resultado da partida.
    """
    try:
        import pandas as pd
        year = year or CURRENT_YEAR

        # Carregar o CSV do ano
        csv_path = SACKMANN_DIR / f"atp_matches_{year}.csv"
        if not csv_path.exists():
            return {}

        df = pd.read_csv(csv_path, low_memory=False)

        # Filtrar por superfície
        if surface:
            surf_val = surface.capitalize()
            df = df[df["surface"] == surf_val]

        # Buscar como vencedor
        name_lower = player_name.lower()
        parts = [p for p in name_lower.split() if len(p) > 2]
        mask_w = df["winner_name"].str.lower().apply(lambda n: isinstance(n, str) and all(p in n for p in parts))
        mask_l = df["loser_name"].str.lower().apply(lambda n: isinstance(n, str) and all(p in n for p in parts))

        df_w = df[mask_w]
        df_l = df[mask_l]
        all_matches = pd.concat([df_w.assign(_side="winner"), df_l.assign(_side="loser")])

        if all_matches.empty:
            return {}

        # Pegar a partida mais recente
        last = all_matches.sort_values("tourney_date", ascending=False).iloc[0]
        side = last["_side"]

        def pct(num, den):
            try:
                n, d = float(num), float(den)
                return f"{round(n/d*100)}%" if d > 0 else "–"
            except Exception:
                return "–"

        if side == "winner":
            stats = {
                "aces":             int(last.get("w_ace", 0)) if str(last.get("w_ace", "nan")) != "nan" else None,
                "double_faults":    int(last.get("w_df", 0))  if str(last.get("w_df", "nan")) != "nan" else None,
                "first_serve_pct":  pct(last.get("w_1stIn"), last.get("w_svpt")),
                "first_serve_won":  pct(last.get("w_1stWon"), last.get("w_1stIn")),
                "second_serve_won": pct(last.get("w_2ndWon"), float(last.get("w_svpt", 0)) - float(last.get("w_1stIn", 0)) if str(last.get("w_svpt","nan")) != "nan" else None),
                "bp_saved_pct":     pct(last.get("w_bpSaved"), last.get("w_bpFaced")),
                "bp_faced":         int(last.get("w_bpFaced", 0)) if str(last.get("w_bpFaced", "nan")) != "nan" else None,
                "bp_saved":         int(last.get("w_bpSaved", 0)) if str(last.get("w_bpSaved", "nan")) != "nan" else None,
            }
            opponent = str(last.get("loser_name", ""))
            won = True
        else:
            stats = {
                "aces":             int(last.get("l_ace", 0))  if str(last.get("l_ace", "nan")) != "nan" else None,
                "double_faults":    int(last.get("l_df", 0))   if str(last.get("l_df", "nan")) != "nan" else None,
                "first_serve_pct":  pct(last.get("l_1stIn"), last.get("l_svpt")),
                "first_serve_won":  pct(last.get("l_1stWon"), last.get("l_1stIn")),
                "second_serve_won": pct(last.get("l_2ndWon"), float(last.get("l_svpt", 0)) - float(last.get("l_1stIn", 0)) if str(last.get("l_svpt","nan")) != "nan" else None),
                "bp_saved_pct":     pct(last.get("l_bpSaved"), last.get("l_bpFaced")),
                "bp_faced":         int(last.get("l_bpFaced", 0)) if str(last.get("l_bpFaced", "nan")) != "nan" else None,
                "bp_saved":         int(last.get("l_bpSaved", 0)) if str(last.get("l_bpSaved", "nan")) != "nan" else None,
            }
            opponent = str(last.get("winner_name", ""))
            won = False

        short = player_name.split()[-1]
        parts_insight = []
        if stats["first_serve_pct"] and stats["first_serve_pct"] != "–":
            parts_insight.append(f"{stats['first_serve_pct']} de 1º saque")
        if stats["first_serve_won"] and stats["first_serve_won"] != "–":
            parts_insight.append(f"{stats['first_serve_won']} de pts no 1º saque")
        if stats["bp_saved_pct"] and stats["bp_saved_pct"] != "–":
            parts_insight.append(f"{stats['bp_saved_pct']} de BPs salvos")

        result_str = "venceu" if won else "perdeu"
        op_short   = opponent.split()[-1]
        insight = f"{short} {result_str} contra {op_short}: {' · '.join(parts_insight)}" if parts_insight else f"Stats de {short} indisponíveis."

        return {
            "player":       player_name,
            "opponent":     opponent,
            "won":          won,
            "tournament":   str(last.get("tourney_name", "")),
            "surface":      str(last.get("surface", "")),
            "score":        str(last.get("score", "")),
            "round":        str(last.get("round", "")),
            "duration_min": int(last.get("minutes", 0)) if str(last.get("minutes", "nan")) != "nan" else None,
            "stats":        stats,
            "insight":      insight,
            "tourney_date": str(last.get("tourney_date", "")),
        }

    except Exception as e:
        log.error(f"get_last_match_stats falhou para {player_name}: {e}")
        return {}


def build_scout_post_data(match_data: dict) -> dict:
    """
    Converte os dados de scout em post_data pronto para generate_post().
    """
    player   = match_data.get("player", "")
    opponent = match_data.get("opponent", "")
    score    = match_data.get("score", "")
    won      = match_data.get("won", True)
    stats    = match_data.get("stats", {})
    duration = match_data.get("duration_min")
    surface  = match_data.get("surface", "Clay").lower()

    short_p = player.split()[-1].upper()
    short_o = opponent.split()[-1]

    # Formatar stats principais
    stat_labels = [
        ("first_serve_pct",  "1º saque"),
        ("first_serve_won",  "pts no 1º saque"),
        ("second_serve_won", "pts no 2º saque"),
        ("bp_saved_pct",     "BPs salvos"),
    ]
    lines = [f"{stats[k]}  {label}" for k, label in stat_labels if stats.get(k) and stats[k] != "–"]
    stats_text = "\n".join(lines) if lines else match_data.get("insight", "")

    title  = f"{short_p} {'VENCE' if won else 'CAI'} CONTRA {short_o.upper()}"
    dur_str = f"  ·  {duration} min" if duration else ""

    return {
        "surface":  surface if surface in ["clay", "hard", "grass"] else "neutral",
        "badge":    "SCOUT",
        "kicker":   f"Scout pós-jogo · {match_data.get('tournament', '')}",
        "title":    title,
        "subtitle": f"{score}{dur_str}\n{stats_text}",
        "image":    "",   # preenchido com foto do vencedor pelo orchestrator
        "credit":   "Stats: Sackmann ATP Dataset",
    }


# ─── Self-test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from dotenv import load_dotenv
    load_dotenv()

    print("=== Última partida — Jannik Sinner (Clay 2025) ===")
    s = get_last_match_stats("Jannik Sinner", surface="Clay", year=2025)
    if s:
        print(f"  vs {s['opponent']}  |  {s['score']}  |  {s['tournament']}  |  {s['round']}")
        print(f"  Stats: {s['stats']}")
        print(f"  Insight: {s['insight']}")
    else:
        print("  Sem dados.")

    print("\n=== Última partida — Carlos Alcaraz (Clay 2025) ===")
    s2 = get_last_match_stats("Carlos Alcaraz", surface="Clay", year=2025)
    if s2:
        print(f"  vs {s2['opponent']}  |  {s2['score']}  |  {s2['tournament']}")
        print(f"  Insight: {s2['insight']}")

    print("\n=== Post data gerado ===")
    if s:
        pd_ = build_scout_post_data(s)
        for k, v in pd_.items():
            if k != "image":
                print(f"  {k}: {v}")
