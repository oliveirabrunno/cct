"""
Pré-carrega fotos dos top N jogadores ATP + WTA no cache local.
Roda uma vez (ou semanalmente) para garantir que partidas relevantes
sempre tenham imagem disponível.

Uso:
    python scripts/prefetch_player_photos.py           # top 100 de cada tour
    python scripts/prefetch_player_photos.py --n 150   # top 150
    python scripts/prefetch_player_photos.py --dry-run # só lista quem falta
"""

import asyncio
import csv
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from utils.image_manager import ImageManager
from utils.logger import get_logger

log = get_logger(__name__)

DATA = Path("data/sackmann")


def _load_player_names(tour: str, top_n: int) -> list[str]:
    """Retorna lista de nomes completos dos top N jogadores pelo ranking atual."""
    rankings_file = DATA / f"tennis_{tour}" / f"{tour}_rankings_current.csv"
    players_file  = DATA / f"tennis_{tour}" / f"{tour}_players.csv"

    if not rankings_file.exists() or not players_file.exists():
        log.error(f"Arquivos de {tour.upper()} não encontrados em {DATA}")
        return []

    # Carregar mapa player_id → nome
    player_map: dict[str, str] = {}
    with open(players_file, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pid = row.get("player_id", "")
            first = row.get("name_first", "").strip()
            last  = row.get("name_last", "").strip()
            if pid and last:
                player_map[pid] = f"{first} {last}".strip()

    # Pegar top N do ranking mais recente
    ranked: list[tuple[int, str]] = []
    with open(rankings_file, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rank = int(row.get("rank", 9999))
            pid  = row.get("player", "")
            if rank <= top_n and pid in player_map:
                ranked.append((rank, player_map[pid]))

    ranked.sort(key=lambda x: x[0])

    # Deduplica mantendo melhor rank (pode haver múltiplas datas no CSV)
    seen: set[str] = set()
    names: list[str] = []
    for _, name in ranked:
        if name not in seen:
            seen.add(name)
            names.append(name)

    return names[:top_n]


def _already_cached(player_name: str) -> bool:
    """True se já há pelo menos 1 foto válida em cache."""
    from utils.image_sources.local_cache import LocalImageCache
    cache = LocalImageCache()
    return cache.get(player_name) is not None


async def prefetch(top_n: int = 100, dry_run: bool = False, tournament_name: str | None = None):
    atp_names = _load_player_names("atp", top_n)
    wta_names = _load_player_names("wta", top_n)

    log.info(f"Top {top_n} ATP: {len(atp_names)} jogadores encontrados")
    log.info(f"Top {top_n} WTA: {len(wta_names)} jogadores encontrados")

    all_names = list(dict.fromkeys(atp_names + wta_names))  # preserva ordem, remove dup
    missing = [n for n in all_names if not _already_cached(n)]

    log.info(f"Já em cache: {len(all_names) - len(missing)} | Precisam de foto: {len(missing)}")

    if dry_run:
        log.info("=== DRY RUN — jogadores sem foto ===")
        for i, name in enumerate(missing, 1):
            log.info(f"  {i:3d}. {name}")
        return

    if not missing:
        log.info("Cache completo — todos os top {top_n} já têm foto.")
        return

    mgr = ImageManager()
    ok = 0
    fail = 0

    for i, name in enumerate(missing, 1):
        log.info(f"[{i}/{len(missing)}] Buscando foto: {name}")
        try:
            result = await mgr.get_player_image(
                name,
                image_type="any",
                download_if_missing=True,
                tournament_name=tournament_name,
            )
            if result and result.get("source") != "placeholder":
                log.info(f"  ✓ {name} → {result['source']} ({result.get('path','').split('/')[-1]})")
                ok += 1
            else:
                log.warning(f"  ✗ {name} — nenhuma foto encontrada")
                fail += 1
        except Exception as e:
            log.error(f"  ✗ {name} — erro: {e}")
            fail += 1

        # Pausa curta entre requests para respeitar rate limits das fontes
        await asyncio.sleep(1.5)

    log.info(f"Prefetch concluído: {ok} fotos baixadas, {fail} sem foto")
    if fail:
        log.info("Jogadores sem foto ficam em placeholder — o card de resultado será bloqueado até terem imagem.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pré-carrega fotos de jogadores no cache local")
    parser.add_argument("--n",       type=int,  default=100, help="Top N jogadores de cada tour (default: 100)")
    parser.add_argument("--dry-run", action="store_true",   help="Só lista quem falta, não baixa nada")
    parser.add_argument("--tournament", type=str, default=None, help="Nome do torneio atual para buscas Flickr mais específicas")
    args = parser.parse_args()

    asyncio.run(prefetch(top_n=args.n, dry_run=args.dry_run, tournament_name=args.tournament))
