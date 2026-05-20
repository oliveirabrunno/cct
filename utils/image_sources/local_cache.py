import json
import os
import re
import aiofiles
import aiohttp
from pathlib import Path
from utils.logger import get_logger

log = get_logger(__name__)

DATA_DIR = Path("data/players")

_RESTORE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def _slug(name: str) -> str:
    import unicodedata
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")


class LocalImageCache:

    def has_any_local_image(self, player_name: str) -> bool:
        """True se existe pelo menos um arquivo físico no cache para este jogador."""
        slug = _slug(player_name)
        player_dir = DATA_DIR / slug
        meta_path = player_dir / "metadata.json"
        if not meta_path.exists():
            return False
        with open(meta_path) as f:
            meta = json.load(f)
        return any((player_dir / p["file"]).exists() for p in meta.get("photos", []))

    def get(self, player_name: str, image_type: str = "any") -> dict | None:
        return self.get_unused(player_name, image_type, exclude_paths=set())

    def get_unused(
        self,
        player_name: str,
        image_type: str = "any",
        exclude_paths: set | None = None,
        exclude_filenames: set | None = None,
    ) -> dict | None:
        """Retorna a primeira foto em cache não presente em exclude_paths nem exclude_filenames."""
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
            photos = filtered if filtered else photos

        excl_paths = exclude_paths or set()
        excl_files = exclude_filenames or set()
        for photo in photos:
            filename = photo["file"]
            file_path = player_dir / filename
            if not file_path.exists():
                continue
            if str(file_path) in excl_paths:
                continue
            if filename in excl_files:
                continue
            return {
                "path":        str(file_path),
                "filename":    filename,
                "source":      photo.get("source", "local"),
                "license":     photo.get("license", ""),
                "credit_text": f"📸 {photo.get('author', 'Wikimedia Commons')}",
            }

        return None

    async def try_restore_from_metadata(
        self,
        player_name: str,
        image_type: str = "any",
        exclude_filenames: set | None = None,
    ) -> dict | None:
        """
        Quando o arquivo físico não existe mas metadata.json tem url_original,
        re-baixa a foto do URL original. Usado para recuperar fotos após cache miss
        no GitHub Actions (arquivos .jpg são gitignored, apenas metadata.json é versionado).
        """
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
            photos = filtered if filtered else photos

        excl_files = exclude_filenames or set()

        for photo in photos:
            filename = photo.get("file", "")
            if not filename or filename in excl_files:
                continue

            file_path = player_dir / filename
            if file_path.exists():
                continue  # arquivo já existe — get_unused deveria tê-lo encontrado

            url = photo.get("url_original", "")
            if not url:
                continue

            try:
                async with aiohttp.ClientSession(headers=_RESTORE_HEADERS) as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        resp.raise_for_status()
                        content = await resp.read()

                async with aiofiles.open(file_path, "wb") as f:
                    await f.write(content)

                log.info(f"Foto restaurada do metadata: {player_name} → {filename}")
                return {
                    "path":        str(file_path),
                    "filename":    filename,
                    "source":      photo.get("source", "local"),
                    "license":     photo.get("license", ""),
                    "credit_text": f"📸 {photo.get('author', 'Wikimedia Commons')}",
                }
            except Exception as e:
                log.warning(f"Falha ao restaurar {filename} para {player_name} ({url}): {e}")
                continue

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
        # Usar timestamp para evitar colisões de filename entre runs do GitHub Actions
        import time as _time
        ts = int(_time.time())
        filename = f"{image_type}_{ts}_{existing + 1:02d}.jpg"
        file_path = player_dir / filename

        url = photo_info.get("url")
        if not url:
            raise ValueError("photo_info sem URL")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        import asyncio
        await asyncio.sleep(0.8)  # respeitar rate limit do Wikimedia
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                resp.raise_for_status()
                content_type = resp.headers.get("Content-Type", "")
                if not content_type.startswith("image/"):
                    raise ValueError(f"URL retornou {content_type} em vez de imagem (WAF/bloqueio)")
                content = await resp.read()

        if len(content) < 5000:
            raise ValueError(f"Imagem muito pequena ({len(content)}B) — provavelmente erro ou placeholder")

        # Validação visual: tamanho e aspect ratio (defesa contra banners/faixas/imagens inválidas)
        try:
            from io import BytesIO
            from PIL import Image as _PILImage
            with _PILImage.open(BytesIO(content)) as im:
                w, h = im.size
            if w < 600 or h < 600:
                raise ValueError(f"Imagem com dimensões pequenas: {w}x{h} (esperado >=600)")
            ratio = max(w, h) / max(1, min(w, h))
            if ratio > 2.5:
                raise ValueError(f"Aspect ratio extremo {ratio:.2f} ({w}x{h}) — possível banner/faixa")
        except ValueError:
            raise
        except Exception as e:
            log.debug(f"Validação PIL falhou (não bloqueante): {e}")

        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        self._update_metadata(player_dir, player_name, slug, filename, image_type, photo_info)
        # Audit log: registrar domínio + source para debug de relevância
        try:
            from urllib.parse import urlparse
            host = urlparse(url).netloc.lower()
            img_source = photo_info.get("source", "unknown")
            log.info(f"Cache: {player_name} → {file_path} (domínio={host}, source={img_source})")
        except Exception:
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
