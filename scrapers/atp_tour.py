"""
Ranking ATP atual via CSV do Sackmann (atualizado semanalmente no GitHub).
Fallback: scraping direto da atptour.com.
"""

import requests
import pandas as pd
from pathlib import Path
from utils.logger import get_logger

log = get_logger(__name__)

SACKMANN_DIR = Path("data/sackmann/tennis_atp")


def fetch_atp_rankings(top_n: int = 20) -> list[dict]:
    """Busca ranking ATP via CSV do Sackmann (atp_rankings_current.csv)."""
    try:
        rankings_file = SACKMANN_DIR / "atp_rankings_current.csv"
        players_file  = SACKMANN_DIR / "atp_players.csv"

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

        log.info(f"ATP ranking (Sackmann): {len(result)} jogadores")
        return result

    except Exception as e:
        log.error(f"Erro ranking ATP Sackmann: {e}")
        return _fallback_ranking("atp")


def fetch_atp_rankings_scrape(top_n: int = 20) -> list[dict]:
    """Fallback: scraping direto do site da ATP com BeautifulSoup."""
    try:
        from bs4 import BeautifulSoup
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        resp = requests.get(ATP_RANKINGS_URL, headers=headers, timeout=20)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        rows = soup.select("table.mega-table tbody tr")[:top_n]

        players = []
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 4:
                continue
            players.append({
                "rank": cols[0].get_text(strip=True),
                "name": cols[1].get_text(strip=True),
                "country": cols[2].get_text(strip=True),
                "points": cols[3].get_text(strip=True).replace(",", ""),
                "move": 0,
            })
        log.info(f"ATP ranking (scrape): {len(players)} jogadores")
        return players

    except Exception as e:
        log.error(f"Scraping ATP falhou: {e}")
        return _fallback_ranking("atp")


def _fallback_ranking(tour: str) -> list[dict]:
    """Ranking estático de emergência (top 10)."""
    if tour == "atp":
        return [
            {"rank": 1, "name": "Jannik Sinner", "country": "ITA", "points": 11830, "move": 0},
            {"rank": 2, "name": "Carlos Alcaraz", "country": "ESP", "points": 9295, "move": 0},
            {"rank": 3, "name": "Alexander Zverev", "country": "GER", "points": 7075, "move": 0},
            {"rank": 4, "name": "Novak Djokovic", "country": "SRB", "points": 6360, "move": 0},
            {"rank": 5, "name": "Daniil Medvedev", "country": "RUS", "points": 5765, "move": 0},
        ]
    return []
