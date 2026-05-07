"""
Head-to-head stats usando CSVs do Jeff Sackmann (tennis_atp / tennis_wta).
Download: https://github.com/JeffSackmann/tennis_atp
          https://github.com/JeffSackmann/tennis_wta
Colocar os arquivos em data/sackmann/
"""

import os
import glob
import pandas as pd
from pathlib import Path
from utils.logger import get_logger

log = get_logger(__name__)

SACKMANN_DIR = Path("data/sackmann")


def _load_matches(tour: str = "atp") -> pd.DataFrame:
    pattern = str(SACKMANN_DIR / f"tennis_{tour}" / f"{tour}_matches_*.csv")
    files = sorted(glob.glob(pattern))

    if not files:
        # Tentar diretamente em data/sackmann/
        pattern = str(SACKMANN_DIR / f"{tour}_matches_*.csv")
        files = sorted(glob.glob(pattern))

    if not files:
        log.warning(f"Nenhum CSV Sackmann encontrado em {SACKMANN_DIR} para tour={tour}")
        return pd.DataFrame()

    dfs = []
    for f in files:
        try:
            df = pd.read_csv(f, low_memory=False)
            dfs.append(df)
        except Exception as e:
            log.error(f"Erro ao ler {f}: {e}")

    if not dfs:
        return pd.DataFrame()

    combined = pd.concat(dfs, ignore_index=True)
    log.info(f"Sackmann {tour.upper()}: {len(combined):,} partidas carregadas")
    return combined


def get_h2h(player_a: str, player_b: str, tour: str = "atp") -> dict:
    df = _load_matches(tour)

    if df.empty:
        return _empty_h2h(player_a, player_b)

    def _norm(name: str) -> str:
        return name.lower().strip()

    a = _norm(player_a)
    b = _norm(player_b)

    # Filtrar apenas partidas entre os dois atletas
    mask = (
        (df["winner_name"].str.lower().str.strip() == a) & (df["loser_name"].str.lower().str.strip() == b)
    ) | (
        (df["winner_name"].str.lower().str.strip() == b) & (df["loser_name"].str.lower().str.strip() == a)
    )

    h2h_df = df[mask].copy()

    if h2h_df.empty:
        log.info(f"H2H: nenhum confronto encontrado entre {player_a} e {player_b}")
        return _empty_h2h(player_a, player_b)

    wins_a = (h2h_df["winner_name"].str.lower().str.strip() == a).sum()
    wins_b = (h2h_df["winner_name"].str.lower().str.strip() == b).sum()

    # Últimas partidas
    recent = h2h_df.sort_values("tourney_date", ascending=False).head(5)
    recent_list = []
    for _, row in recent.iterrows():
        recent_list.append({
            "date": str(row.get("tourney_date", "")),
            "tournament": row.get("tourney_name", ""),
            "surface": row.get("surface", ""),
            "round": row.get("round", ""),
            "winner": row.get("winner_name", ""),
            "score": row.get("score", ""),
        })

    return {
        "player_a": player_a,
        "player_b": player_b,
        "total_matches": len(h2h_df),
        "wins_a": int(wins_a),
        "wins_b": int(wins_b),
        "recent_matches": recent_list,
        "surfaces": {
            s: {
                "wins_a": int((h2h_df[h2h_df["surface"] == s]["winner_name"].str.lower().str.strip() == a).sum()),
                "wins_b": int((h2h_df[h2h_df["surface"] == s]["winner_name"].str.lower().str.strip() == b).sum()),
            }
            for s in h2h_df["surface"].dropna().unique()
        },
    }


def get_player_stats(player_name: str, tour: str = "atp", year: int | None = None) -> dict:
    df = _load_matches(tour)
    if df.empty:
        return {}

    name = player_name.lower().strip()

    wins_mask = df["winner_name"].str.lower().str.strip() == name
    losses_mask = df["loser_name"].str.lower().str.strip() == name

    if year:
        df["year"] = df["tourney_date"].astype(str).str[:4]
        wins_mask = wins_mask & (df["year"] == str(year))
        losses_mask = losses_mask & (df["year"] == str(year))

    wins = df[wins_mask]
    losses = df[losses_mask]

    return {
        "player": player_name,
        "year": year or "carreira",
        "wins": len(wins),
        "losses": len(losses),
        "win_pct": round(len(wins) / (len(wins) + len(losses)) * 100, 1) if (len(wins) + len(losses)) > 0 else 0,
        "titles": int(wins[wins["round"] == "F"].shape[0]),
        "surfaces": {
            s: {"wins": int((wins["surface"] == s).sum()), "losses": int((losses["surface"] == s).sum())}
            for s in ["Hard", "Clay", "Grass"]
        },
    }


def _empty_h2h(player_a: str, player_b: str) -> dict:
    return {
        "player_a": player_a,
        "player_b": player_b,
        "total_matches": 0,
        "wins_a": 0,
        "wins_b": 0,
        "recent_matches": [],
        "surfaces": {},
    }
