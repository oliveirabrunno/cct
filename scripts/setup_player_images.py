"""
Setup inicial do banco de imagens.
Rodar UMA VEZ para popular data/players/ com fotos do Wikimedia.

Uso: python scripts/setup_player_images.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from utils.image_manager import ImageManager
from utils.logger import get_logger

log = get_logger(__name__)

TOP_50_ATP = [
    "Jannik Sinner", "Carlos Alcaraz", "Alexander Zverev", "Novak Djokovic",
    "Daniil Medvedev", "Casper Ruud", "Andrey Rublev", "Holger Rune",
    "Stefanos Tsitsipas", "Taylor Fritz", "Ben Shelton", "Ugo Humbert",
    "Felix Auger-Aliassime", "Tommy Paul", "Alex de Minaur", "Grigor Dimitrov",
    "Sebastian Korda", "Karen Khachanov", "Frances Tiafoe", "Lorenzo Musetti",
    "Francisco Cerundolo", "Alejandro Davidovich Fokina", "Tallon Griekspoor",
    "Matteo Arnaldi", "Hubert Hurkacz", "Arthur Fils", "Tomas Machac",
    "Jiri Lehecka", "Nicolas Jarry", "Joao Fonseca",
]

TOP_50_WTA = [
    "Aryna Sabalenka", "Iga Swiatek", "Coco Gauff", "Jessica Pegula",
    "Elena Rybakina", "Jasmine Paolini", "Madison Keys", "Emma Navarro",
    "Mirra Andreeva", "Daria Kasatkina", "Marketa Vondrousova",
    "Maria Sakkari", "Beatriz Haddad Maia", "Victoria Azarenka",
]

# Prioridade máxima — setup estes primeiro
PRIORITY = [
    "Joao Fonseca", "Jannik Sinner", "Carlos Alcaraz", "Iga Swiatek",
    "Aryna Sabalenka", "Novak Djokovic", "Beatriz Haddad Maia", "Coco Gauff",
]


async def setup_player(manager: ImageManager, player: str):
    log.info(f"Processando {player}...")
    try:
        r1 = await manager.get_player_image(player, "headshot", download_if_missing=True)
        r2 = await manager.get_player_image(player, "action", download_if_missing=True)
        ok = sum(1 for r in [r1, r2] if r and r.get("source") != "placeholder")
        log.info(f"  {player}: {ok}/2 imagens reais obtidas")
    except Exception as e:
        log.error(f"  {player}: ERRO — {e}")
    await asyncio.sleep(2)  # rate limiting Wikimedia


async def main():
    manager = ImageManager()

    all_players = PRIORITY + [p for p in (TOP_50_ATP + TOP_50_WTA) if p not in PRIORITY]
    log.info(f"Setup iniciado: {len(all_players)} atletas")

    for player in all_players:
        await setup_player(manager, player)

    log.info(f"Setup concluído: {len(all_players)} atletas processados")
    log.info("Imagens salvas em data/players/")


if __name__ == "__main__":
    asyncio.run(main())
