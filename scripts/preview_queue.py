"""
Exibe preview formatado do conteúdo na fila (output/queue/).
Útil para revisar antes de publicar.

Uso: python scripts/preview_queue.py
"""

import json
from pathlib import Path
from datetime import datetime

QUEUE_DIR = Path("output/queue")

RESET = "\033[0m"
BOLD  = "\033[1m"
CYAN  = "\033[96m"
GREEN = "\033[92m"
YELLOW= "\033[93m"


def fmt_size(path: Path) -> str:
    if path.exists():
        kb = path.stat().st_size / 1024
        return f"{kb:.0f}KB" if kb < 1024 else f"{kb/1024:.1f}MB"
    return "?"


def preview_folder(folder: Path) -> None:
    name = folder.name
    ts_str = name[:19].replace("_", " ").replace("-", "/", 2).replace("_", " ", 1)

    if "carousel" in name:
        tipo = "📸 CARROSSEL"
        slides = sorted(folder.glob("slide_*.png"))
        detail = f"{len(slides)} slides"
    elif "reel" in name:
        tipo = "🎬 REEL"
        videos = list(folder.glob("reel.*"))
        detail = fmt_size(videos[0]) if videos else "?"
    elif "story" in name:
        tipo = "📲 STORY"
        images = list(folder.glob("story.*"))
        detail = fmt_size(images[0]) if images else "?"
    else:
        tipo = "📄 OUTRO"
        detail = ""

    caption_file = folder / "legenda.txt"
    caption = ""
    if caption_file.exists():
        text = caption_file.read_text(encoding="utf-8")
        caption = text.split("\n")[0][:80] + ("..." if len(text) > 80 else "")

    print(f"\n{BOLD}{tipo}{RESET} {CYAN}{ts_str}{RESET} ({detail})")
    if caption:
        print(f"  {YELLOW}{caption}{RESET}")
    print(f"  📁 {folder}")


def preview_standalone(file: Path) -> None:
    ext = file.suffix.lower()
    if ext == ".mp4":
        tipo = "🎬 REEL (standalone)"
    elif ext == ".png":
        tipo = "📸 PNG (standalone)"
    else:
        return
    print(f"\n{BOLD}{tipo}{RESET} {CYAN}{file.name}{RESET} ({fmt_size(file)})")


if __name__ == "__main__":
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"  Café com Tênis — Fila de Publicação")
    print(f"{'='*60}")

    if not QUEUE_DIR.exists() or not list(QUEUE_DIR.iterdir()):
        print("\nFila vazia.")
    else:
        items = sorted(QUEUE_DIR.iterdir(), key=lambda x: x.name)
        folders = [i for i in items if i.is_dir()]
        files   = [i for i in items if i.is_file()]

        for f in folders:
            preview_folder(f)
        for f in files:
            preview_standalone(f)

    print(f"\n{BOLD}Total:{RESET} {len(list(QUEUE_DIR.iterdir()))} item(s)\n")
