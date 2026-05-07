"""
Rankings ATP e WTA em tempo real via live-tennis.eu.
Atualizado a cada ponto jogado — muito mais preciso que os CSVs semanais do Sackmann.

URLs:
  ATP live: https://live-tennis.eu/en/atp-live-ranking
  WTA live: https://live-tennis.eu/en/wta-live-ranking
"""

import requests
from bs4 import BeautifulSoup
from utils.logger import get_logger

log = get_logger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

URLS = {
    "atp": "https://live-tennis.eu/en/atp-live-ranking",
    "wta": "https://live-tennis.eu/en/wta-live-ranking",
}


def _parse_ranking(url: str, top_n: int) -> list[dict]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.encoding = "utf-8"
        resp.raise_for_status()
    except Exception as e:
        log.error(f"live-tennis.eu falhou ({url}): {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    tbody = soup.find("tbody")
    if not tbody:
        log.error("Tabela não encontrada em live-tennis.eu")
        return []

    players = []
    for row in tbody.find_all("tr"):
        cols = row.find_all("td")
        if len(cols) < 7:
            continue

        rank_str   = cols[0].get_text(strip=True)
        move_str   = cols[1].get_text(strip=True)
        name       = cols[3].get_text(strip=True)
        country    = cols[5].get_text(strip=True)
        points_str = cols[6].get_text(strip=True)
        change_str = cols[8].get_text(strip=True) if len(cols) > 8 else ""

        try:
            rank = int(rank_str)
        except ValueError:
            continue

        if rank > top_n:
            break

        # move: CH = sem mudança, número = posições subidas/descidas
        try:
            move = int(move_str)
        except ValueError:
            move = 0

        try:
            points = int(points_str.replace(",", ""))
        except ValueError:
            points = 0

        players.append({
            "rank":    rank,
            "name":    name,
            "country": country,
            "points":  points,
            "move":    move,
            "change":  change_str,
        })

    log.info(f"live-tennis.eu: {len(players)} jogadores")
    return players


def fetch_atp_live_rankings(top_n: int = 20) -> list[dict]:
    result = _parse_ranking(URLS["atp"], top_n)
    if not result:
        log.warning("Fallback para scrapers/atp_tour.py (Sackmann)")
        from scrapers.atp_tour import fetch_atp_rankings
        return fetch_atp_rankings(top_n)
    return result


def fetch_wta_live_rankings(top_n: int = 20) -> list[dict]:
    result = _parse_ranking(URLS["wta"], top_n)
    if not result:
        log.warning("Fallback para scrapers/wta_tour.py (Sackmann)")
        from scrapers.wta_tour import fetch_wta_rankings
        return fetch_wta_rankings(top_n)
    return result


def fetch_player_ranking(player_name: str, tour: str = "atp") -> dict | None:
    """Busca a posição ao vivo de um jogador específico."""
    top100 = fetch_atp_live_rankings(100) if tour == "atp" else fetch_wta_live_rankings(100)
    name_lower = player_name.lower()
    for p in top100:
        if name_lower in p["name"].lower() or p["name"].lower() in name_lower:
            return p
    return None


if __name__ == "__main__":
    print("=== ATP Live Top 10 ===")
    for p in fetch_atp_live_rankings(10):
        move_str = f"({'↑' if p['move'] > 0 else '↓'}{abs(p['move'])})" if p["move"] else ""
        print(f"#{p['rank']:>3} {p['name']:<30} {p['country']} {p['points']:>6} pts {move_str}")

    print("\n=== WTA Live Top 10 ===")
    for p in fetch_wta_live_rankings(10):
        print(f"#{p['rank']:>3} {p['name']:<30} {p['country']} {p['points']:>6} pts")
