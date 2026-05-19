"""
Dados de chaveamento de torneios ATP/WTA.
Tenta scraping do ATP/WTA Tour e live-tennis.eu.
Fallback: projeção por seed (mesma abordagem do @tennischannel).
"""

import re
import requests
from datetime import date
from bs4 import BeautifulSoup
from utils.logger import get_logger

log = get_logger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Configuração do torneio atual.
# ATUALIZAR entries_atp e entries_wta no início de cada torneio novo —
# a ordem define o seed (posição 0 = seed #1). Usar isso evita o problema
# de colocar jogadores ausentes no chave (ex: Alcaraz fora de Roma).
CURRENT_TOURNAMENT = {
    "name": "Roland Garros",
    "short": "Roland Garros",
    "surface": "clay",
    "category": "Grand Slam",
    "draw_size": 128,
    "date": "24 maio–7 jun 2026",
    "location": "Paris, França",
    "atp_id": "520",
    "atp_slug": "roland-garros",
    "wta_id": "1840",
    "wta_slug": "roland-garros",
    "next_name": "Wimbledon",
    "next_date": "29 jun–12 jul 2026",

    # Inscritos confirmados — atualizar quando draw oficial for liberado (23 mai)
    # Alcaraz LESIONADO — não incluir até confirmação de participação
    "entries_atp": [
        "Jannik Sinner",           # seed 1
        "Alexander Zverev",        # seed 2
        "Novak Djokovic",          # seed 3
        "Casper Ruud",             # seed 4 (especialista no saibro)
        "Daniil Medvedev",         # seed 5
        "Holger Rune",             # seed 6
        "Taylor Fritz",            # seed 7
        "Alex de Minaur",          # seed 8
        "Stefanos Tsitsipas",      # seed 9
        "Grigor Dimitrov",         # seed 10
        "Ben Shelton",             # seed 11
        "Felix Auger-Aliassime",   # seed 12
        "Hubert Hurkacz",          # seed 13
        "Andrey Rublev",           # seed 14
        "Tommy Paul",              # seed 15
        "Ugo Humbert",             # seed 16
        # --- não-cabeças relevantes ---
        "João Fonseca",            # ~#29-30 no ranking
        "Thiago Seyboth Wild",     # brasileiro
    ],
    "entries_wta": [
        "Aryna Sabalenka",         # seed 1
        "Iga Swiatek",             # seed 2 (4x campeã em Paris)
        "Coco Gauff",              # seed 3
        "Elena Rybakina",          # seed 4
        "Jessica Pegula",          # seed 5
        "Mirra Andreeva",          # seed 6
        "Qinwen Zheng",            # seed 7
        "Emma Navarro",            # seed 8
        # --- brasileiras ---
        "Beatriz Haddad Maia",     # ranking WTA a confirmar
    ],

    # Brasileiros em destaque (sempre no carrossel independente do seed)
    "brazilians_atp": ["João Fonseca", "Thiago Seyboth Wild"],
    "brazilians_wta": ["Beatriz Haddad Maia"],

    # Quantos seeds oficiais o torneio tem por tour
    "num_seeds_atp": 16,
    "num_seeds_wta": 8,
}


# --- Mapeamento de seed → adversário projetado no chave Masters 1000 ---
# Baseado na estrutura padrão de draw 96/128 com byes para cabeças de chave
# "possible path" — mesma lógica do @tennischannel
SEED_PATH_ATP = {
    1: [
        {"round": "2ª Rodada",    "projected_seed": None,   "label": "Lucky Loser ou Qualifier"},
        {"round": "3ª Rodada",    "projected_seed": "17-24","label": ""},
        {"round": "Quartas",      "projected_seed": "5-8",  "label": ""},
        {"round": "Semifinal",    "projected_seed": "3-4",  "label": ""},
        {"round": "Final",        "projected_seed": "2",    "label": ""},
    ],
    2: [
        {"round": "2ª Rodada",    "projected_seed": None,   "label": "Lucky Loser ou Qualifier"},
        {"round": "3ª Rodada",    "projected_seed": "17-24","label": ""},
        {"round": "Quartas",      "projected_seed": "5-8",  "label": ""},
        {"round": "Semifinal",    "projected_seed": "3-4",  "label": ""},
        {"round": "Final",        "projected_seed": "1",    "label": ""},
    ],
    3: [
        {"round": "1ª Rodada",    "projected_seed": None,   "label": "Qualifier"},
        {"round": "2ª Rodada",    "projected_seed": "17-24","label": ""},
        {"round": "3ª Rodada",    "projected_seed": "11-16","label": ""},
        {"round": "Quartas",      "projected_seed": "6-8",  "label": ""},
        {"round": "Semifinal",    "projected_seed": "1-2",  "label": ""},
        {"round": "Final",        "projected_seed": "1-2",  "label": ""},
    ],
    4: [
        {"round": "1ª Rodada",    "projected_seed": None,   "label": "Qualifier"},
        {"round": "2ª Rodada",    "projected_seed": "17-24","label": ""},
        {"round": "3ª Rodada",    "projected_seed": "11-16","label": ""},
        {"round": "Quartas",      "projected_seed": "5-8",  "label": ""},
        {"round": "Semifinal",    "projected_seed": "1-2",  "label": ""},
        {"round": "Final",        "projected_seed": "1-2",  "label": ""},
    ],
}

# Para seeds 5-16 e não-cabeças (genérico)
SEED_PATH_GENERIC = [
    {"round": "1ª Rodada",  "projected_seed": None,   "label": "adversário do draw"},
    {"round": "2ª Rodada",  "projected_seed": "17-32","label": ""},
    {"round": "3ª Rodada",  "projected_seed": "9-16", "label": ""},
    {"round": "Quartas",    "projected_seed": "3-4",  "label": ""},
    {"round": "Semifinal",  "projected_seed": "1-2",  "label": ""},
    {"round": "Final",      "projected_seed": "1-2",  "label": ""},
]


def _try_scrape_atp_draw(tournament_slug: str, tournament_id: str) -> list[dict]:
    """Tenta pegar o draw real do ATP Tour."""
    url = f"https://www.atptour.com/en/scores/current/{tournament_slug}/{tournament_id}/draws"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        players = []
        # ATP usa tabelas com classes específicas
        for row in soup.select("tr.scores-draw-entry-box-table-row"):
            seed_el = row.select_one(".scores-draw-entry-box-seed")
            name_el = row.select_one(".scores-draw-entry-box-player-name")
            if name_el:
                seed_str = seed_el.get_text(strip=True) if seed_el else ""
                try:
                    seed = int(re.sub(r"\D", "", seed_str)) if seed_str else 0
                except ValueError:
                    seed = 0
                players.append({
                    "name": name_el.get_text(strip=True),
                    "seed": seed,
                })

        if players:
            log.info(f"ATP Tour draw: {len(players)} jogadores")
        return players
    except Exception as e:
        log.warning(f"ATP draw scraping falhou: {e}")
        return []


def _match_name(search: str, candidate: str) -> bool:
    s, c = search.lower(), candidate.lower()
    return s in c or c in s or any(w in c for w in s.split() if len(w) > 3)


def get_tournament_seeds(tour: str = "atp") -> list[dict]:
    """
    Retorna seeds do torneio usando entries_atp/entries_wta do CURRENT_TOURNAMENT.
    Enriquece com ranking/pontos do live-tennis.eu.
    """
    t = CURRENT_TOURNAMENT
    entry_key = f"entries_{tour}"
    entries = t.get(entry_key, [])

    if not entries:
        log.warning(f"entries_{tour} vazio — fallback para live ranking")
        try:
            if tour == "atp":
                from scrapers.live_ranking import fetch_atp_live_rankings
                players = fetch_atp_live_rankings(32)
            else:
                from scrapers.live_ranking import fetch_wta_live_rankings
                players = fetch_wta_live_rankings(32)
            return [{"seed": i+1, "rank": p["rank"], "name": p["name"],
                     "country": p["country"], "points": p["points"]}
                    for i, p in enumerate(players[:16])]
        except Exception as e:
            log.error(f"Não foi possível obter seeds: {e}")
            return []

    # Buscar pontos/país do live ranking para enriquecer
    try:
        if tour == "atp":
            from scrapers.live_ranking import fetch_atp_live_rankings
            live = fetch_atp_live_rankings(50)
        else:
            from scrapers.live_ranking import fetch_wta_live_rankings
            live = fetch_wta_live_rankings(50)
    except Exception:
        live = []

    live_index = {p["name"].lower(): p for p in live}

    num_seeds = t.get(f"num_seeds_{tour}", 12)
    seeds = []
    for i, entry_name in enumerate(entries):
        # Tentar achar no live ranking por nome parcial
        live_data = next(
            (p for name, p in live_index.items() if _match_name(entry_name, name)),
            None,
        )
        seed_num = i + 1 if i < num_seeds else 0
        seeds.append({
            "seed":    seed_num,
            "rank":    live_data["rank"]    if live_data else "?",
            "name":    entry_name,
            "country": live_data["country"] if live_data else "",
            "points":  live_data["points"]  if live_data else 0,
        })

    log.info(f"Entries {tour.upper()}: {len(seeds)} jogadores")
    return seeds


def get_projected_path(player_name: str, tour: str = "atp") -> dict:
    """
    Retorna o caminho projetado do jogador no torneio atual.
    Usa entries confirmadas — não coloca jogador ausente no chave.
    """
    t = CURRENT_TOURNAMENT
    seeds = get_tournament_seeds(tour)

    player_info = next(
        (s for s in seeds if _match_name(player_name, s["name"])),
        {"seed": 0, "rank": "?", "name": player_name, "country": ""},
    )
    player_seed = player_info.get("seed", 0)

    if player_seed in SEED_PATH_ATP:
        path_template = SEED_PATH_ATP[player_seed]
    else:
        path_template = SEED_PATH_GENERIC

    path = []
    for step in path_template:
        seed_range = step["projected_seed"]
        opponent_name = step["label"] or "adversário"

        if seed_range and str(seed_range).isdigit():
            s = int(seed_range)
            opp = next((x for x in seeds if x["seed"] == s), None)
            if opp:
                opponent_name = f"{opp['name']} (#{s})"
        elif seed_range and "-" in str(seed_range):
            parts = seed_range.split("-")
            s_min, s_max = int(parts[0]), int(parts[1])
            candidates = [x for x in seeds if s_min <= x["seed"] <= s_max]
            if candidates:
                opponent_name = " ou ".join(
                    f"{c['name']} (#{c['seed']})" for c in candidates[:2]
                )

        path.append({"round": step["round"], "opponent": opponent_name})

    return {
        "tournament":     t["name"],
        "short":          t["short"],
        "surface":        t["surface"],
        "category":       t["category"],
        "date":           t["date"],
        "location":       t["location"],
        "next_name":      t.get("next_name", ""),
        "next_date":      t.get("next_date", ""),
        "player":         player_info["name"],
        "player_seed":    player_seed,
        "player_rank":    player_info.get("rank", "?"),
        "player_country": player_info.get("country", ""),
        "path":           path,
        "top_seeds":      [s for s in seeds if s["seed"] > 0][:8],
    }


def get_tournament_overview(tour: str = "atp") -> dict:
    """
    Retorna estrutura completa para o carrossel de visão geral do torneio.
    Top 4 seeds confirmados + brasileiros em destaque.
    """
    t = CURRENT_TOURNAMENT
    seeds = get_tournament_seeds(tour)

    top4 = [s for s in seeds if 1 <= s["seed"] <= 4]
    bra_key = f"brazilians_{tour}"
    bra_names = t.get(bra_key, [])

    brazilians = []
    for bra_name in bra_names:
        bra_info = next((s for s in seeds if _match_name(bra_name, s["name"])), None)
        if bra_info:
            path = get_projected_path(bra_info["name"], tour)
            brazilians.append({**bra_info, "path": path["path"]})

    # Path resumido para cada top 4
    top4_with_path = []
    for player in top4:
        path = get_projected_path(player["name"], tour)
        top4_with_path.append({**player, "path": path["path"]})

    return {
        "tournament": t["name"],
        "short":      t["short"],
        "surface":    t["surface"],
        "category":   t["category"],
        "date":       t["date"],
        "location":   t["location"],
        "next_name":  t.get("next_name", ""),
        "tour":       tour.upper(),
        "top4":       top4_with_path,
        "brazilians": brazilians,
    }


if __name__ == "__main__":
    print("=== ATP ===")
    ov = get_tournament_overview("atp")
    for p in ov["top4"]:
        print(f"  #{p['seed']} {p['name']}")
        for step in p["path"]:
            print(f"    {step['round']}: vs {step['opponent']}")
    print("\nBrasileiros ATP:")
    for b in ov["brazilians"]:
        print(f"  {b['name']} (seed #{b['seed']})")

    print("\n=== WTA ===")
    ov_wta = get_tournament_overview("wta")
    for p in ov_wta["top4"]:
        print(f"  #{p['seed']} {p['name']}")
