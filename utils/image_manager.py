import os
from utils.image_sources.local_cache import LocalImageCache
from utils.image_sources.wikimedia import get_player_photos
from utils.image_sources.wikipedia_profile import get_profile_photo
from utils.image_sources.player_instagram import get_player_recent_photo
from utils.image_sources.google_images import search_cc_player_photo
from utils.logger import get_logger

log = get_logger(__name__)

_FLICKR_AVAILABLE = bool(os.getenv("FLICKR_API_KEY", ""))


class ImageManager:

    def __init__(self):
        self.cache = LocalImageCache()
        self._used_paths: set[str] = set()

    def reset_session(self):
        self._used_paths.clear()

    async def get_player_image(
        self,
        player_name: str,
        image_type: str = "any",
        download_if_missing: bool = True,
        tournament_name: str | None = None,
    ) -> dict | None:
        if not player_name:
            return self._get_placeholder("Desconhecido")

        # 1. Cache local — foto já baixada e verificada
        cached = self.cache.get_unused(player_name, image_type, exclude_paths=self._used_paths)
        if cached:
            self._used_paths.add(cached["path"])
            log.info(f"Cache local: {player_name} → {cached['path'].split('/')[-1]}")
            return cached

        if not download_if_missing:
            return self._get_placeholder(player_name)

        # 2. Flickr — fonte primária: CC, alta qualidade, aware do torneio atual
        if _FLICKR_AVAILABLE:
            result = await self._try_flickr(player_name, image_type, tournament_name)
            if result:
                return result

        # 3. Wikipedia profile — headshot confiável para jogadores conhecidos
        if image_type in ("headshot", "any"):
            result = await self._try_wikipedia_profile(player_name, image_type)
            if result:
                return result

        # 4. Wikimedia Commons — fallback com busca por nome
        result = await self._try_wikimedia(player_name, image_type)
        if result:
            return result

        # 5. Wikipedia profile como fallback de action (melhor que nada)
        if image_type not in ("headshot", "any"):
            result = await self._try_wikipedia_profile(player_name, "any")
            if result:
                return result

        # 6. Instagram oficial
        ig_photo = await get_player_recent_photo(player_name)
        if ig_photo:
            try:
                local_path = await self.cache.download_and_save(player_name, ig_photo, image_type)
                if local_path not in self._used_paths:
                    self._used_paths.add(local_path)
                    return {
                        "path":        local_path,
                        "source":      "instagram",
                        "license":     "editorial",
                        "credit_text": f"📸 @{ig_photo['handle']}",
                    }
            except Exception as e:
                log.error(f"Instagram download falhou para {player_name}: {e}")

        log.warning(f"Nenhuma imagem encontrada para '{player_name}' — placeholder")
        return self._get_placeholder(player_name)

    # ── Fontes individuais ────────────────────────────────────────────────────

    async def _try_flickr(
        self,
        player_name: str,
        image_type: str,
        tournament_name: str | None = None,
    ) -> dict | None:
        from utils.dedup import is_duplicate_image_url, register_image_url
        try:
            from utils.image_sources.flickr import search_player_images as flickr_search
            photos = flickr_search(
                player_name,
                count=6,
                tournament_name=tournament_name,
            )
            for photo in photos:
                url = photo.get("url", "")
                if not url:
                    continue
                # Evitar reusar mesma imagem entre sessões
                if is_duplicate_image_url(url):
                    log.debug(f"Flickr URL já usada, pulando: {url.split('/')[-1][:40]}")
                    continue
                try:
                    local_path = await self.cache.download_and_save(player_name, photo, image_type)
                    if local_path not in self._used_paths:
                        self._used_paths.add(local_path)
                        register_image_url(url, player=player_name, source="flickr")
                        log.info(f"Flickr: {player_name} → {local_path.split('/')[-1]}")
                        return {
                            "path":        local_path,
                            "source":      "flickr",
                            "license":     photo.get("license", "CC BY 2.0"),
                            "credit_text": f"📸 Flickr — {photo.get('author', '')}",
                        }
                except Exception as e:
                    log.debug(f"Flickr download falhou ({player_name}): {e}")
        except Exception as e:
            log.warning(f"Flickr indisponível: {e}")
        return None

    async def _try_wikipedia_profile(self, player_name: str, image_type: str) -> dict | None:
        from utils.dedup import is_duplicate_image_url, register_image_url
        try:
            photo = get_profile_photo(player_name)
            if not photo:
                return None
            url = photo.get("url", "")
            if url and is_duplicate_image_url(url):
                log.debug(f"Wikipedia URL já usada para {player_name}")
                return None
            local_path = await self.cache.download_and_save(player_name, photo, image_type)
            if local_path not in self._used_paths:
                self._used_paths.add(local_path)
                if url:
                    register_image_url(url, player=player_name, source="wikipedia")
                log.info(f"Wikipedia: {player_name} → {local_path.split('/')[-1]}")
                return {
                    "path":        local_path,
                    "source":      "wikipedia",
                    "license":     photo.get("license", "CC"),
                    "credit_text": "📸 Wikipedia Commons",
                }
        except Exception as e:
            log.debug(f"Wikipedia profile falhou ({player_name}): {e}")
        return None

    async def _try_wikimedia(self, player_name: str, image_type: str) -> dict | None:
        from utils.dedup import is_duplicate_image_url, register_image_url
        for photo in get_player_photos(player_name, count=4):
            url = photo.get("url", "")
            if url and is_duplicate_image_url(url):
                log.debug(f"Wikimedia URL já usada, pulando")
                continue
            try:
                local_path = await self.cache.download_and_save(player_name, photo, image_type)
                if local_path not in self._used_paths:
                    self._used_paths.add(local_path)
                    if url:
                        register_image_url(url, player=player_name, source="wikimedia")
                    return {
                        "path":        local_path,
                        "source":      "wikimedia",
                        "license":     photo["license"],
                        "credit_text": f"📸 Wikimedia — {photo.get('author', '')}",
                    }
            except Exception as e:
                log.debug(f"Wikimedia download falhou para {player_name}: {e}")
        return None

    def _get_placeholder(self, player_name: str) -> dict:
        initials = "".join(w[0].upper() for w in player_name.split()[:2])
        return {
            "path":        None,
            "initials":    initials,
            "source":      "placeholder",
            "license":     "generated",
            "credit_text": "",
        }
