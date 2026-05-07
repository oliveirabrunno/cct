"""
Atualiza os fatos fixos no base_voice.txt com dados em tempo real do live-tennis.eu.
Chamado automaticamente no início de cada pipeline diário.
"""

from pathlib import Path
from utils.logger import get_logger

log = get_logger(__name__)

PROMPT_PATH = Path("config/prompts/base_voice.txt")

BRASILEIROS_ATP = ["Fonseca", "Monteiro", "Matos"]
BRASILEIRAS_WTA  = ["Haddad", "Bia"]


def update_facts():
    try:
        from scrapers.live_ranking import fetch_atp_live_rankings, fetch_wta_live_rankings
        atp = fetch_atp_live_rankings(50)
        wta = fetch_wta_live_rankings(50)
    except Exception as e:
        log.error(f"Não foi possível buscar ranking ao vivo: {e}")
        return

    lines = []

    # Top 5 ATP
    lines.append("RANKING AO VIVO — ATP (atualizado automaticamente):")
    for p in atp[:10]:
        bra = " 🇧🇷" if p["country"] == "BRA" else ""
        lines.append(f"  #{p['rank']} {p['name']} ({p['country']}) — {p['points']} pts{bra}")

    lines.append("")

    # Top 10 WTA
    lines.append("RANKING AO VIVO — WTA:")
    for p in wta[:10]:
        bra = " 🇧🇷" if p["country"] == "BRA" else ""
        lines.append(f"  #{p['rank']} {p['name']} ({p['country']}) — {p['points']} pts{bra}")

    lines.append("")

    # Brasileiros em destaque
    bra_atp = [p for p in atp if p["country"] == "BRA"]
    bra_wta = [p for p in wta if p["country"] == "BRA"]
    if bra_atp:
        lines.append("BRASILEIROS NO ATP:")
        for p in bra_atp:
            lines.append(f"  #{p['rank']} {p['name']} — {p['points']} pts")
    if bra_wta:
        lines.append("BRASILEIRAS NO WTA:")
        for p in bra_wta:
            lines.append(f"  #{p['rank']} {p['name']} — {p['points']} pts")

    ranking_block = "\n".join(lines)

    # Ler arquivo atual e substituir o bloco de ranking
    current = PROMPT_PATH.read_text(encoding="utf-8")

    # Delimitar bloco com marcadores
    start_marker = "<!-- RANKING_AUTO_START -->"
    end_marker   = "<!-- RANKING_AUTO_END -->"

    new_block = f"{start_marker}\n{ranking_block}\n{end_marker}"

    if start_marker in current:
        import re
        current = re.sub(
            rf"{re.escape(start_marker)}.*?{re.escape(end_marker)}",
            new_block,
            current,
            flags=re.DOTALL,
        )
    else:
        current = current.rstrip() + "\n\n" + new_block + "\n"

    PROMPT_PATH.write_text(current, encoding="utf-8")
    log.info(f"base_voice.txt atualizado: {len(atp)} ATP + {len(wta)} WTA jogadores")


if __name__ == "__main__":
    update_facts()
