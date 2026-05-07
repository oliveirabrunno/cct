"""
Ranking WTA atual via CSV do Sackmann (wta_rankings_current.csv).
"""

import pandas as pd
from pathlib import Path
from utils.logger import get_logger

log = get_logger(__name__)

SACKMANN_DIR = Path("data/sackmann/tennis_wta")


def fetch_wta_rankings(top_n: int = 20) -> list[dict]:
    try:
        rankings_file = SACKMANN_DIR / "wta_rankings_current.csv"
        players_file  = SACKMANN_DIR / "wta_players.csv"

        if not rankings_file.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {rankings_file}")

        df_rank = pd.read_csv(rankings_file)
        latest_date = df_rank["ranking_date"].max()
        df_rank = df_rank[df_rank["ranking_date"] == latest_date].sort_values("rank").head(top_n)

        players_map = {}
        if players_file.exists():
            df_players = pd.read_csv(players_file, low_memory=False)
            for _, row in df_players.iterrows():
                pid = str(int(row["player_id"])) if not pd.isna(row["player_id"]) else ""
                name = f"{row['name_first']} {row['name_last']}"
                country = str(row.get("ioc", ""))
                players_map[pid] = {"name": name, "country": country}

        result = []
        for _, row in df_rank.iterrows():
            pid = str(int(row["player"]))
            info = players_map.get(pid, {"name": f"Player {pid}", "country": ""})
            result.append({
                "rank": int(row["rank"]),
                "name": info["name"],
                "country": info["country"],
                "points": int(row.get("points", 0)),
                "move": 0,
            })

        log.info(f"WTA ranking (Sackmann): {len(result)} jogadoras")
        return result

    except Exception as e:
        log.error(f"Erro ranking WTA Sackmann: {e}")
        return _fallback_ranking()


def _fallback_ranking() -> list[dict]:
    return [
        {"rank": 1, "name": "Aryna Sabalenka", "country": "BLR", "points": 10935, "move": 0},
        {"rank": 2, "name": "Iga Swiatek", "country": "POL", "points": 9665, "move": 0},
        {"rank": 3, "name": "Coco Gauff", "country": "USA", "points": 6765, "move": 0},
        {"rank": 4, "name": "Jessica Pegula", "country": "USA", "points": 5705, "move": 0},
        {"rank": 5, "name": "Elena Rybakina", "country": "KAZ", "points": 5475, "move": 0},
    ]
