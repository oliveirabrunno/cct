"""
Publica conteúdo da fila local (output/queue/) para o Instagram via Meta Graph API.
Útil quando o pipeline rodou em modo local e o Meta já está configurado.

Uso:
    # Publicar tudo na fila
    python scripts/publish_from_queue.py

    # Publicar apenas um item específico
    python scripts/publish_from_queue.py output/queue/2026-05-06_13-25-30_carousel
"""

import asyncio
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from utils.logger import get_logger

load_dotenv()
log = get_logger(__name__)

QUEUE_DIR = Path("output/queue")
PUBLISHED_DIR = Path("output/published")


async def publish_folder(folder: Path, publisher) -> bool:
    folder_type = "carousel" if "carousel" in folder.name else \
                  "reel" if "reel" in folder.name else \
                  "story" if "story" in folder.name else "unknown"

    caption_file = folder / "legenda.txt"
    caption = caption_file.read_text(encoding="utf-8") if caption_file.exists() else ""

    log.info(f"Publicando {folder.name} ({folder_type})...")

    if folder_type == "carousel":
        slides = sorted(folder.glob("slide_*.png"))
        if not slides:
            log.error(f"Sem slides em {folder}")
            return False
        return await publisher.publish_carousel([str(s) for s in slides], caption)

    elif folder_type == "reel":
        video = next(folder.glob("reel.*"), None)
        if not video:
            log.error(f"Sem vídeo em {folder}")
            return False
        return await publisher.publish_reel(str(video), caption)

    elif folder_type == "story":
        image = next(folder.glob("story.*"), None)
        if not image:
            log.error(f"Sem imagem em {folder}")
            return False
        poll_config = None
        poll_file = folder / "poll_config.json"
        if poll_file.exists():
            poll_config = json.loads(poll_file.read_text())
        return await publisher.publish_story(str(image), poll_config)

    log.warning(f"Tipo desconhecido: {folder_type}")
    return False


async def main():
    from publisher.graph_publisher import GraphPublisher
    publisher = GraphPublisher()

    if len(sys.argv) > 1:
        folders = [Path(sys.argv[1])]
    else:
        folders = sorted(
            [f for f in QUEUE_DIR.iterdir() if f.is_dir()],
            key=lambda f: f.name
        )

    if not folders:
        log.info("Fila vazia — nada a publicar")
        return

    log.info(f"Publicando {len(folders)} item(s) da fila...")
    published = []
    failed = []

    for folder in folders:
        try:
            ok = await publish_folder(folder, publisher)
            if ok:
                published.append(folder.name)
                # Mover para published/
                PUBLISHED_DIR.mkdir(exist_ok=True)
                folder.rename(PUBLISHED_DIR / folder.name)
            else:
                failed.append(folder.name)
        except Exception as e:
            log.error(f"{folder.name}: {e}")
            failed.append(folder.name)

    log.info(f"\n✅ Publicados: {len(published)}")
    for name in published:
        print(f"  ✓ {name}")

    if failed:
        log.warning(f"❌ Falhas: {len(failed)}")
        for name in failed:
            print(f"  ✗ {name}")


if __name__ == "__main__":
    asyncio.run(main())
