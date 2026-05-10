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

        # Carregar filenames usados recentemente do SQLite (evita repetição entre runs)
        from utils.dedup import get_used_image_filenames, register_used_image
        used_files = get_used_image_filenames(player_name)

        # 1. Cache local — foto já baixada e verificada
        cached = self.cache.get_unused(
            player_name, image_type,
            exclude_paths=self._used_paths,
            exclude_filenames=used_files,
        )
        if cached:
            self._used_paths.add(cached["path"])
            register_used_image(player_name, cached["filename"])
            log.info(f"Cache local: {player_name} → {cached['path'].split('/')[-1]}")
            return cached

        if not download_if_missing:
            return self._get_placeholder(player_name)

        # 2. Restore do metadata — re-baixa foto do url_original quando arquivo
        #    não existe em disco (típico após cache miss no GitHub Actions).
        #    Executa ANTES do Flickr para evitar requests desnecessários.
        restored = await self.cache.try_restore_from_metadata(
            player_name, image_type, exclude_filenames=set(used_files)
        )
        if restored:
            self._used_paths.add(restored["path"])
            try:
                register_used_image(player_name, restored["filename"])
            except Exception:
                pass
            return restored

        # 4. Flickr — fonte primária: CC, alta qualidade, aware do torneio atual
        if _FLICKR_AVAILABLE:
            result = await self._try_flickr(player_name, image_type, tournament_name)
            if result:
                return result

        # 5. Wikipedia profile — headshot confiável para jogadores conhecidos
        if image_type in ("headshot", "any"):
            result = await self._try_wikipedia_profile(player_name, image_type)
            if result:
                return result

        # 6. Wikimedia Commons — fallback com busca por nome
        result = await self._try_wikimedia(player_name, image_type)
        if result:
            return result

        # 7. Wikipedia profile como fallback de action (melhor que nada)
        if image_type not in ("headshot", "any"):
            result = await self._try_wikipedia_profile(player_name, "any")
            if result:
                return result

        # 8. Instagram oficial
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
                try:
                    local_path = await self.cache.download_and_save(player_name, photo, image_type)
                    if local_path not in self._used_paths:
                        self._used_paths.add(local_path)
                        fname = local_path.split("/")[-1]
                        try:
                            register_used_image(player_name, fname)
                        except Exception:
                            pass
                        log.info(f"Flickr: {player_name} → {fname}")
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
        from utils.dedup import register_used_image
        try:
            photo = get_profile_photo(player_name)
            if not photo:
                return None
            local_path = await self.cache.download_and_save(player_name, photo, image_type)
            if local_path not in self._used_paths:
                self._used_paths.add(local_path)
                fname = local_path.split("/")[-1]
                try:
                    register_used_image(player_name, fname)
                except Exception:
                    pass
                log.info(f"Wikipedia: {player_name} → {fname}")
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
        from utils.dedup import register_used_image
        for photo in get_player_photos(player_name, count=4):
            try:
                local_path = await self.cache.download_and_save(player_name, photo, image_type)
                if local_path not in self._used_paths:
                    self._used_paths.add(local_path)
                    fname = local_path.split("/")[-1]
                    try:
                        register_used_image(player_name, fname)
                    except Exception:
                        pass
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
