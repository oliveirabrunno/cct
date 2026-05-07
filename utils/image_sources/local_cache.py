import json
import os
import re
import aiofiles
import aiohttp
from pathlib import Path
from utils.logger import get_logger

log = get_logger(__name__)

DATA_DIR = Path("data/players")


def _slug(name: str) -> str:
    import unicodedata
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")


class LocalImageCache:

    def get(self, player_name: str, image_type: str = "any") -> dict | None:
        return self.get_unused(player_name, image_type, exclude_paths=set())

    def get_unused(
        self,
        player_name: str,
        image_type: str = "any",
        exclude_paths: set | None = None,
    ) -> dict | None:
        """Retorna a primeira foto em cache não presente em exclude_paths."""
        slug = _slug(player_name)
        player_dir = DATA_DIR / slug
        meta_path = player_dir / "metadata.json"

        if not meta_path.exists():
            return None

        with open(meta_path) as f:
            meta = json.load(f)

        photos = meta.get("photos", [])
        if image_type != "any":
            filtered = [p for p in photos if p.get("type") == image_type]
            # Se não encontrou pelo tipo exato, usa todas
            photos = filtered if filtered else photos

        exclude = exclude_paths or set()
        for photo in photos:
            file_path = player_dir / photo["file"]
            if not file_path.exists():
                continue
            path_str = str(file_path)
            if path_str in exclude:
                continue
            return {
                "path": path_str,
                "source": photo.get("source", "local"),
                "license": photo.get("license", ""),
                "credit_text": f"📸 {photo.get('author', 'Wikimedia Commons')}",
            }

        return None

    async def download_and_save(
        self,
        player_name: str,
        photo_info: dict,
        image_type: str = "any",
    ) -> str:
        slug = _slug(player_name)
        player_dir = DATA_DIR / slug
        player_dir.mkdir(parents=True, exist_ok=True)

        existing = self._count_files(player_dir, image_type)
        filename = f"{image_type}_{existing + 1:02d}.jpg"
        file_path = player_dir / filename

        url = photo_info.get("url")
        if not url:
            raise ValueError("photo_info sem URL")

        headers = {
            "User-Agent": "CafeComTenis/1.0 (https://instagram.com/cafecomteniss; cafecomtenis@gmail.com)"
        }
        import asyncio
        await asyncio.sleep(0.8)  # respeitar rate limit do Wikimedia
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                resp.raise_for_status()
                content = await resp.read()

        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        self._update_metadata(player_dir, player_name, slug, filename, image_type, photo_info)
        log.info(f"Cache: {player_name} → {file_path}")
        return str(file_path)

    def _count_files(self, player_dir: Path, image_type: str) -> int:
        meta_path = player_dir / "metadata.json"
        if not meta_path.exists():
            return 0
        with open(meta_path) as f:
            meta = json.load(f)
        return sum(1 for p in meta.get("photos", []) if p.get("type") == image_type)

    def _update_metadata(
        self,
        player_dir: Path,
        player_name: str,
        slug: str,
        filename: str,
        image_type: str,
        photo_info: dict,
    ) -> None:
        meta_path = player_dir / "metadata.json"
        from datetime import date

        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
        else:
            meta = {"player": player_name, "slug": slug, "photos": []}

        meta["photos"].append({
            "file": filename,
            "type": image_type,
            "source": photo_info.get("source", ""),
            "license": photo_info.get("license", ""),
            "author": photo_info.get("author", ""),
            "url_original": photo_info.get("url", ""),
            "downloaded_at": date.today().isoformat(),
        })

        with open(meta_path, "w") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
