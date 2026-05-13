"""
Stats Scraper — dados reais de tênis para o pipeline de insights.

Fontes:
  1. Sackmann CSV (já disponível localmente) — H2H, surface record, stats de saque/devolução
  2. atptour.com/en/stats — líderes de stat da temporada (BeautifulSoup)
  3. Tennis Abstract — Elo rating e stats avançadas

Sem APIs pagas.
"""

import os
import re
import requests
from pathlib import Path
from datetime import date
from utils.logger import get_logger

log = get_logger(__name__)

SACKMANN_DIR = Path("data/sackmann/tennis_atp")
SACKMANN_WTA_DIR = Path("data/sackmann/tennis_wta")

CURRENT_YEAR = date.today().year

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _load_sackmann_years(start_year: int = 2015, end_year: int = None, tour: str = "atp"):
    """Carrega e concatena CSVs do Sackmann para um intervalo de anos."""
    try:
        import pandas as pd
    except ImportError:
        log.error("pandas não instalado")
        return None

    end_year = end_year or CURRENT_YEAR
    dfs = []
    base_dir = SACKMANN_DIR if tour == "atp" else SACKMANN_WTA_DIR

    for year in range(start_year, end_year + 1):
        csv_path = base_dir / f"{tour}_matches_{year}.csv"
        if csv_path.exists():
            try:
                df = pd.read_csv(csv_path, low_memory=False)
                dfs.append(df)
            except Exception as e:
                log.debug(f"Erro ao ler {csv_path}: {e}")

    if not dfs:
        log.warning(f"Nenhum CSV Sackmann encontrado em {base_dir}")
        return None

    import pandas as pd
    return pd.concat(dfs, ignore_index=True)


def _find_player_in_df(df, player_name: str, col: str):
    """Busca flexível por nome de jogador numa coluna do DataFrame."""
    name_lower = player_name.lower().strip()
    parts = [p for p in name_lower.split() if len(p) > 2]
    mask = df[col].str.lower().apply(
        lambda n: isinstance(n, str) and all(p in n for p in parts)
    )
    return mask


# ─── H2H Real ─────────────────────────────────────────────────────────────────

def get_h2h(player_a: str, player_b: str, surface: str = None, since_year: int = 2015) -> dict:
    """
    Calcula H2H real entre dois jogadores via Sackmann CSV.
    
    Returns:
        {
            "player_a": str, "player_b": str,
            "wins_a": int, "wins_b": int, "total": int,
            "surface": str,
            "last_matches": list[dict],   # últimas 5 partidas
            "clay_a": int, "clay_b": int,
            "hard_a": int, "hard_b": int,
            "grass_a": int, "grass_b": int,
            "insight": str                # frase pronta para o post
        }
    """
    df = _load_sackmann_years(start_year=since_year)
    if df is None:
        return _h2h_fallback(player_a, player_b)

    mask_a_win = _find_player_in_df(df, player_a, "winner_name") & _find_player_in_df(df, player_b, "loser_name")
    mask_b_win = _find_player_in_df(df, player_b, "winner_name") & _find_player_in_df(df, player_a, "loser_name")
    mask_any   = mask_a_win | mask_b_win

    matches = df[mask_any].copy()

    if surface:
        surf_map = {"clay": "Clay", "hard": "Hard", "grass": "Grass"}
        surf_val  = surf_map.get(surface.lower(), surface.capitalize())
        matches   = matches[matches["surface"] == surf_val]

    wins_a = int(mask_a_win[mask_any].sum()) if not matches.empty else 0
    wins_b = int(mask_b_win[mask_any].sum()) if not matches.empty else 0

    # Por superfície (independente do filtro acima)
    all_matches = df[mask_any]

    def surf_wins(player, df_sub, surf_val):
        m = _find_player_in_df(df_sub, player, "winner_name") & (df_sub["surface"] == surf_val)
        return int(m.sum())

    clay_a  = surf_wins(player_a, all_matches, "Clay")
    clay_b  = surf_wins(player_b, all_matches, "Clay")
    hard_a  = surf_wins(player_a, all_matches, "Hard")
    hard_b  = surf_wins(player_b, all_matches, "Hard")
    grass_a = surf_wins(player_a, all_matches, "Grass")
    grass_b = surf_wins(player_b, all_matches, "Grass")

    # Últimas 5 partidas
    last5 = []
    if not all_matches.empty:
        recent = all_matches.sort_values("tourney_date", ascending=False).head(5)
        for _, row in recent.iterrows():
            winner_is_a = all(p in str(row["winner_name"]).lower() for p in [p for p in player_a.lower().split() if len(p) > 2])
            last5.append({
                "winner": row["winner_name"],
                "loser":  row["loser_name"],
                "score":  row.get("score", ""),
                "surface": row.get("surface", ""),
                "tournament": row.get("tourney_name", ""),
                "year": str(row.get("tourney_date", ""))[:4],
            })

    # Gerar insight textual
    total = wins_a + wins_b
    a_short = player_a.split()[-1]
    b_short = player_b.split()[-1]
    surf_label = f" no {surface}" if surface else ""

    if total == 0:
        insight = f"Primeiro confronto entre {a_short} e {b_short}{surf_label}."
    elif wins_a > wins_b:
        insight = f"{a_short} domina o H2H{surf_label}: {wins_a}-{wins_b} desde {since_year}."
    elif wins_b > wins_a:
        insight = f"{b_short} domina o H2H{surf_label}: {wins_b}-{wins_a} desde {since_year}."
    else:
        insight = f"Confronto equilibrado{surf_label}: {wins_a}-{wins_b} desde {since_year}."

    return {
        "player_a": player_a,
        "player_b": player_b,
        "wins_a": wins_a,
        "wins_b": wins_b,
        "total": total,
        "surface": surface,
        "clay_a": clay_a, "clay_b": clay_b,
        "hard_a": hard_a, "hard_b": hard_b,
        "grass_a": grass_a, "grass_b": grass_b,
        "last_matches": last5,
        "insight": insight,
    }


def _h2h_fallback(player_a: str, player_b: str) -> dict:
    a_short = player_a.split()[-1]
    b_short = player_b.split()[-1]
    return {
        "player_a": player_a, "player_b": player_b,
        "wins_a": 0, "wins_b": 0, "total": 0,
        "surface": None,
        "clay_a": 0, "clay_b": 0,
        "hard_a": 0, "hard_b": 0,
        "grass_a": 0, "grass_b": 0,
        "last_matches": [],
        "insight": f"H2H de {a_short} vs {b_short} indisponível.",
    }


# ─── Performance por Superfície ───────────────────────────────────────────────

def get_surface_record(player_name: str, year: int = None, tour: str = "atp") -> dict:
    """
    Calcula W/L por superfície do jogador no ano especificado (default: ano atual).

    Returns:
        {
            "player": str,
            "year": int,
            "clay":  {"wins": int, "losses": int, "pct": str},
            "hard":  {"wins": int, "losses": int, "pct": str},
            "grass": {"wins": int, "losses": int, "pct": str},
            "best_surface": str,
            "insight": str
        }
    """
    year = year or CURRENT_YEAR
    df = _load_sackmann_years(start_year=year, end_year=year, tour=tour)
    if df is None:
        return _surface_fallback(player_name, year)

    def record(df_sub, player, surf_val):
        wins   = int(_find_player_in_df(df_sub[df_sub["surface"] == surf_val], player, "winner_name").sum())
        losses = int(_find_player_in_df(df_sub[df_sub["surface"] == surf_val], player, "loser_name").sum())
        total  = wins + losses
        pct    = f"{round(wins/total*100)}%" if total > 0 else "–"
        return {"wins": wins, "losses": losses, "pct": pct, "total": total}

    clay  = record(df, player_name, "Clay")
    hard  = record(df, player_name, "Hard")
    grass = record(df, player_name, "Grass")

    surfaces = {"Clay": clay, "Hard": hard, "Grass": grass}
    best = max(surfaces, key=lambda s: surfaces[s]["wins"] if surfaces[s]["total"] > 0 else -1)

    short = player_name.split()[-1]
    best_rec = surfaces[best]
    insight = (
        f"{short} tem {best_rec['wins']}-{best_rec['losses']} ({best_rec['pct']}) "
        f"no {best} em {year}."
    )

    return {
        "player": player_name,
        "year": year,
        "clay": clay,
        "hard": hard,
        "grass": grass,
        "best_surface": best,
        "insight": insight,
    }


def _surface_fallback(player_name: str, year: int) -> dict:
    short = player_name.split()[-1]
    empty = {"wins": 0, "losses": 0, "pct": "–", "total": 0}
    return {
        "player": player_name, "year": year,
        "clay": empty, "hard": empty, "grass": empty,
        "best_surface": "–",
        "insight": f"Dados de superfície de {short} indisponíveis.",
    }


# ─── Stats de Saque/Devolução ─────────────────────────────────────────────────

def get_serve_stats(player_name: str, year: int = None, surface: str = None) -> dict:
    """
    Calcula médias de saque a partir dos dados Sackmann (% 1º saque, aces, DFs).
    
    Returns:
        {
            "player": str,
            "first_serve_pct": str,
            "first_serve_won_pct": str,
            "second_serve_won_pct": str,
            "ace_per_game": str,
            "bp_save_pct": str,
            "matches_analyzed": int,
            "insight": str
        }
    """
    import pandas as pd

    year = year or CURRENT_YEAR
    df = _load_sackmann_years(start_year=year, end_year=year)
    if df is None:
        return {"player": player_name, "insight": "Dados indisponíveis."}

    # Filtrar como vencedor (temos stats de saque do vencedor)
    mask_w = _find_player_in_df(df, player_name, "winner_name")
    mask_l = _find_player_in_df(df, player_name, "loser_name")

    if surface:
        surf_val = surface.capitalize()
        mask_w = mask_w & (df["surface"] == surf_val)
        mask_l = mask_l & (df["surface"] == surf_val)

    df_w = df[mask_w].copy()
    df_l = df[mask_l].copy()
    # Renomear colunas do perdedor para o mesmo padrão
    df_l = df_l.rename(columns={
        "l_svpt": "w_svpt", "l_1stIn": "w_1stIn",
        "l_1stWon": "w_1stWon", "l_2ndWon": "w_2ndWon",
        "l_SvGms": "w_SvGms", "l_bpSaved": "w_bpSaved",
        "l_bpFaced": "w_bpFaced", "l_ace": "w_ace", "l_df": "w_df",
    })

    cols_w = ["w_svpt", "w_1stIn", "w_1stWon", "w_2ndWon", "w_SvGms", "w_bpSaved", "w_bpFaced", "w_ace", "w_df"]
    cols_l = ["l_svpt", "l_1stIn", "l_1stWon", "l_2ndWon", "l_SvGms", "l_bpSaved", "l_bpFaced", "l_ace", "l_df"]
    rename_map = {f"l_{c[2:]}": f"w_{c[2:]}" for c in cols_l}

    df_w_sel = df_w[[c for c in cols_w if c in df_w.columns]].copy()
    df_l_raw = df_l[[c for c in cols_l if c in df_l.columns]].copy()
    df_l_sel = df_l_raw.rename(columns=rename_map)

    df_all = pd.concat([df_w_sel, df_l_sel], ignore_index=True).dropna()

    if df_all.empty:
        return {"player": player_name, "insight": f"Sem dados de saque para {player_name.split()[-1]}."}

    totals = df_all.sum()
    matches = len(df_all)

    svpt     = totals["w_svpt"]
    first_in = totals["w_1stIn"]
    first_won = totals["w_1stWon"]
    second_won = totals["w_2ndWon"]
    second_pts = svpt - first_in
    bp_saved = totals["w_bpSaved"]
    bp_faced = totals["w_bpFaced"]
    sv_gms   = totals["w_SvGms"]
    aces     = totals["w_ace"]

    def pct(num, den):
        return f"{round(num/den*100)}%" if den > 0 else "–"

    first_pct      = pct(first_in, svpt)
    first_won_pct  = pct(first_won, first_in)
    second_won_pct = pct(second_won, second_pts)
    bp_save_pct    = pct(bp_saved, bp_faced)
    ace_pg         = f"{aces/sv_gms:.1f}" if sv_gms > 0 else "–"

    short = player_name.split()[-1]
    surf_label = f" no {surface}" if surface else ""
    insight = (
        f"{short}{surf_label} em {year}: {first_pct} de 1º saque, "
        f"{first_won_pct} de pts ganhos no 1º saque, "
        f"{bp_save_pct} de break points salvos."
    )

    return {
        "player": player_name,
        "first_serve_pct": first_pct,
        "first_serve_won_pct": first_won_pct,
        "second_serve_won_pct": second_won_pct,
        "ace_per_game": ace_pg,
        "bp_save_pct": bp_save_pct,
        "matches_analyzed": int(matches),
        "insight": insight,
    }


# ─── Líderes de Stat (Season) via ATP Tour scraping ───────────────────────────

def get_atp_stat_leaders(stat_type: str = "aces", surface: str = None, top_n: int = 10) -> list[dict]:
    """
    Scraping dos líderes de estatística em atptour.com/en/stats.

    stat_type: "aces" | "first-serve" | "first-serve-points-won" |
               "break-points-converted" | "break-points-saved" | "return-points-won"
    surface: "clay" | "hard" | "grass" | None (todos)
    """
    STAT_MAP = {
        "aces":                      "Aces",
        "first-serve":               "% 1º Saque",
        "first-serve-points-won":    "% Pts Ganhos no 1º Saque",
        "second-serve-points-won":   "% Pts Ganhos no 2º Saque",
        "break-points-converted":    "% Break Points Convertidos",
        "break-points-saved":        "% Break Points Salvos",
        "return-points-won":         "% Pontos de Devolução Ganhos",
    }

    url = f"https://www.atptour.com/en/stats/leaderboard?boardType=stats&timeframe=52weeks&surface={surface or 'all'}&stat={stat_type}&slim=true"

    try:
        from bs4 import BeautifulSoup
        resp = requests.get(url, headers=_HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        rows = soup.select("table tbody tr")[:top_n]
        results = []
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 3:
                continue
            results.append({
                "rank":   cols[0].get_text(strip=True),
                "player": cols[1].get_text(strip=True),
                "value":  cols[-1].get_text(strip=True),
                "stat":   STAT_MAP.get(stat_type, stat_type),
            })

        if results:
            log.info(f"ATP stat leaders ({stat_type}): {len(results)} jogadores")
            return results

    except Exception as e:
        log.warning(f"Scraping ATP stats falhou ({stat_type}): {e}")

    # Fallback via Sackmann para os stats mais comuns
    return _stat_leaders_sackmann_fallback(stat_type, surface, top_n)


def _stat_leaders_sackmann_fallback(stat_type: str, surface: str, top_n: int) -> list[dict]:
    """Calcula líderes de stat via Sackmann para o ano corrente."""
    try:
        import pandas as pd
        df = _load_sackmann_years(start_year=CURRENT_YEAR, end_year=CURRENT_YEAR)
        if df is None:
            return []

        if surface:
            surf_val = surface.capitalize()
            df = df[df["surface"] == surf_val]

        stat_col_map = {
            "aces":                    ("w_ace", "Aces por Jogo"),
            "break-points-saved":      ("w_bpSaved", "% Break Points Salvos"),
            "break-points-converted":  ("w_bpSaved", "% Break Points Salvos"),  # proxy via Sackmann
            "first-serve":             ("w_1stIn",   "% 1º Saque"),
        }

        if stat_type not in stat_col_map:
            return []

        col, label = stat_col_map[stat_type]

        agg = df.groupby("winner_name")[col].sum().reset_index()
        agg = agg.sort_values(col, ascending=False).head(top_n)

        return [
            {"rank": str(i+1), "player": row["winner_name"],
             "value": str(round(row[col], 1)), "stat": label}
            for i, (_, row) in enumerate(agg.iterrows())
        ]

    except Exception as e:
        log.warning(f"Fallback Sackmann falhou: {e}")
        return []


# ─── Self-test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    print("\n=== H2H: Sinner vs Alcaraz (Saibro) ===")
    h2h = get_h2h("Jannik Sinner", "Carlos Alcaraz", surface="clay")
    print(f"  {h2h['wins_a']}-{h2h['wins_b']}  |  {h2h['insight']}")
    print(f"  Clay: {h2h['clay_a']}-{h2h['clay_b']}  Hard: {h2h['hard_a']}-{h2h['hard_b']}  Grass: {h2h['grass_a']}-{h2h['grass_b']}")
    if h2h["last_matches"]:
        print(f"  Último: {h2h['last_matches'][0]}")

    print("\n=== Surface Record: Jannik Sinner 2025 ===")
    rec = get_surface_record("Jannik Sinner", year=2025)
    print(f"  Clay: {rec['clay']['wins']}-{rec['clay']['losses']} ({rec['clay']['pct']})")
    print(f"  Hard: {rec['hard']['wins']}-{rec['hard']['losses']} ({rec['hard']['pct']})")
    print(f"  Insight: {rec['insight']}")

    print("\n=== Serve Stats: Carlos Alcaraz 2025 ===")
    srv = get_serve_stats("Carlos Alcaraz", year=2025, surface="clay")
    print(f"  {srv.get('insight', 'N/A')}")

    print("\n=== ATP Stat Leaders: Aces 2025 ===")
    leaders = get_atp_stat_leaders("aces", surface="clay", top_n=5)
    for l in leaders:
        print(f"  {l['rank']}. {l['player']} — {l['value']}")
