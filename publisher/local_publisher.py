"""
Publisher local para Semanas 1-2.
Salva PNGs + legenda em /output/queue/ para revisão e postagem manual.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from utils.logger import get_logger

log = get_logger(__name__)

QUEUE_DIR = Path("output/queue")


class LocalPublisher:

    async def publish_carousel(self, images: list[str], caption: str, hashtags: list[str] = None) -> bool:
        folder = self._new_queue_folder("carousel")

        for i, img_path in enumerate(images, 1):
            src = Path(img_path)
            if src.exists():
                shutil.copy(src, folder / f"slide_{i:02d}{src.suffix}")

        self._write_caption(folder, caption, hashtags)
        log.info(f"Carrossel salvo em {folder} — {len(images)} slides")
        return True

    async def publish_post(self, image: str, caption: str, hashtags: list[str] = None) -> bool:
        """Post simples (imagem única). Alias para publish_single."""
        return await self.publish_single(image, caption, hashtags)

    async def publish_single(self, image: str, caption: str, hashtags: list[str] = None) -> bool:
        folder = self._new_queue_folder("post")
        src = Path(image)
        if src.exists():
            shutil.copy(src, folder / f"post{src.suffix}")
        self._write_caption(folder, caption, hashtags)
        log.info(f"Post salvo em {folder}")
        return True

    async def publish_reel(self, video: str, caption: str, hashtags: list[str] = None) -> bool:
        folder = self._new_queue_folder("reel")
        src = Path(video)
        if src.exists():
            shutil.copy(src, folder / f"reel{src.suffix}")
        self._write_caption(folder, caption, hashtags)
        log.info(f"Reel salvo em {folder}")
        return True

    async def publish_story(self, image: str, poll_config: dict = None) -> bool:
        folder = self._new_queue_folder("story")
        src = Path(image)
        if src.exists():
            shutil.copy(src, folder / f"story{src.suffix}")
        if poll_config:
            (folder / "poll_config.json").write_text(
                json.dumps(poll_config, ensure_ascii=False, indent=2)
            )
        log.info(f"Story salvo em {folder}")
        return True

    def _new_queue_folder(self, post_type: str) -> Path:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        folder = QUEUE_DIR / f"{ts}_{post_type}"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _write_caption(self, folder: Path, caption: str, hashtags: list[str] = None) -> None:
        full = caption
        if hashtags:
            full += "\n\n" + " ".join(f"#{h.lstrip('#')}" for h in hashtags)
        (folder / "legenda.txt").write_text(full, encoding="utf-8")
