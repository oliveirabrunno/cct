"""
Publisher via Meta Graph API (oficial, gratuito).
Pré-requisitos:
  - Conta Instagram Business vinculada a uma Facebook Page
  - META_ACCESS_TOKEN e META_IG_USER_ID no .env
  - Token com permissões: instagram_basic, instagram_content_publish, pages_read_engagement

Documentação: https://developers.facebook.com/docs/instagram-api/guides/content-publishing
"""

import os
import time
import requests
from pathlib import Path
from utils.logger import get_logger
from publisher.rate_limiter import can_publish_feed_post

log = get_logger(__name__)

GRAPH_API = "https://graph.facebook.com/v19.0"
ACCESS_TOKEN  = os.getenv("META_ACCESS_TOKEN", "")
IG_USER_ID    = os.getenv("META_IG_USER_ID", "")


def _headers() -> dict:
    return {"Authorization": f"Bearer {ACCESS_TOKEN}"}


class GraphPublisher:

    def __init__(self):
        if not ACCESS_TOKEN or not IG_USER_ID:
            log.warning("META_ACCESS_TOKEN ou META_IG_USER_ID não configurados")

    # ─── CARROSSEL ────────────────────────────────────────────────────────────

    async def publish_carousel(
        self, images: list[str], caption: str, hashtags: list[str] = None
    ) -> bool:
        if not self._is_configured():
            return False
        if not can_publish_feed_post():
            log.warning("Carousel não publicado — quota diária atingida")
            return False

        # Meta Graph API exige mínimo 2 e máximo 10 imagens por carrossel
        if not images or len(images) < 2:
            log.error(
                f"publish_carousel abortado — {len(images) if images else 0} imagem(s) "
                "fornecida(s), mínimo exigido pelo Meta: 2"
            )
            return False
        if len(images) > 10:
            log.warning(f"Carrossel tem {len(images)} slides — truncando para 10 (limite Meta)")
            images = images[:10]

        # Validar que todos os arquivos existem antes de iniciar uploads
        for img_path in images:
            if not img_path or not Path(img_path).exists():
                log.error(
                    f"publish_carousel abortado — arquivo inválido ou inexistente: {img_path}"
                )
                return False

        full_caption = self._build_caption(caption, hashtags)

        # 1. Criar container para cada imagem
        item_ids = []
        for img_path in images:
            item_id = self._create_image_container(img_path, is_carousel_item=True)
            if not item_id:
                log.error(f"Falha ao criar container para {img_path}")
                return False
            item_ids.append(item_id)
            time.sleep(1)  # respeitar rate limit

        # 2. Criar container do carrossel
        carousel_id = self._create_carousel_container(item_ids, full_caption)
        if not carousel_id:
            return False

        # 3. Aguardar processamento dos containers antes de publicar
        time.sleep(8)
        return self._publish_container(carousel_id)

    # ─── POST ÚNICO ───────────────────────────────────────────────────────────

    async def publish_single(self, image: str, caption: str, hashtags: list[str] = None) -> bool:
        if not self._is_configured():
            return False
        if not can_publish_feed_post():
            log.warning("Post único não publicado — quota diária atingida")
            return False
        if not image or not Path(image).exists():
            log.error(f"publish_single abortado — arquivo inválido ou inexistente: {image}")
            return False
        full_caption = self._build_caption(caption, hashtags)
        container_id = self._create_image_container(image, caption=full_caption)
        if not container_id:
            return False
        time.sleep(8)  # aguardar processamento da imagem pelo Meta antes de publicar
        return self._publish_container(container_id)

    async def publish_post(self, image: str, caption: str, hashtags: list[str] = None) -> bool:
        """Alias de publish_single para consistência de interface."""
        return await self.publish_single(image, caption, hashtags)

    # ─── REEL ─────────────────────────────────────────────────────────────────

    async def publish_reel(self, video: str, caption: str, hashtags: list[str] = None) -> bool:
        if not self._is_configured():
            return False
        if not can_publish_feed_post():
            log.warning("Reel não publicado — quota diária atingida")
            return False
        full_caption = self._build_caption(caption, hashtags)
        container_id = self._create_video_container(video, full_caption)
        if not container_id:
            return False
        # Reels precisam de polling até status FINISHED
        return self._wait_and_publish(container_id)

    # ─── STORY ────────────────────────────────────────────────────────────────

    async def publish_story(self, image: str, poll_config: dict = None) -> bool:
        if not self._is_configured():
            return False
        container_id = self._create_image_container(image, media_type="STORIES")
        if not container_id:
            return False
        return self._publish_container(container_id)

    # ─── INTERNOS ─────────────────────────────────────────────────────────────

    def _create_image_container(
        self,
        image_path: str,
        caption: str = "",
        is_carousel_item: bool = False,
        media_type: str = "IMAGE",
    ) -> str | None:
        image_url = self._upload_image(image_path)
        if not image_url:
            return None

        params = {
            "image_url": image_url,
            "access_token": ACCESS_TOKEN,
        }
        if caption:
            params["caption"] = caption
        if is_carousel_item:
            params["is_carousel_item"] = "true"
        if media_type != "IMAGE":
            params["media_type"] = media_type

        resp = requests.post(
            f"{GRAPH_API}/{IG_USER_ID}/media", params=params, timeout=30
        )
        data = resp.json()
        if "id" not in data:
            log.error(f"Erro ao criar container de imagem: {data}")
            return None
        log.info(f"Container criado: {data['id']}")
        return data["id"]

    def _create_carousel_container(self, item_ids: list[str], caption: str) -> str | None:
        params = {
            "media_type": "CAROUSEL",
            "children": ",".join(item_ids),
            "caption": caption,
            "access_token": ACCESS_TOKEN,
        }
        resp = requests.post(
            f"{GRAPH_API}/{IG_USER_ID}/media", params=params, timeout=30
        )
        data = resp.json()
        if "id" not in data:
            log.error(f"Erro ao criar container carrossel: {data}")
            return None
        log.info(f"Container carrossel: {data['id']}")
        return data["id"]

    def _create_video_container(self, video_path: str, caption: str) -> str | None:
        video_url = self._upload_video(video_path)
        if not video_url:
            return None
        params = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "access_token": ACCESS_TOKEN,
        }
        resp = requests.post(
            f"{GRAPH_API}/{IG_USER_ID}/media", params=params, timeout=30
        )
        data = resp.json()
        if "id" not in data:
            log.error(f"Erro ao criar container de reel: {data}")
            return None
        return data["id"]

    def _publish_container(self, container_id: str) -> bool:
        params = {
            "creation_id": container_id,
            "access_token": ACCESS_TOKEN,
        }
        resp = requests.post(
            f"{GRAPH_API}/{IG_USER_ID}/media_publish", params=params, timeout=30
        )
        data = resp.json()
        if "id" in data:
            log.info(f"Publicado! Post ID: {data['id']}")
            return True
        log.error(f"Erro ao publicar: {data}")
        return False

    def _wait_and_publish(self, container_id: str, max_wait: int = 300) -> bool:
        """Aguarda processamento de vídeo antes de publicar."""
        waited = 0
        while waited < max_wait:
            resp = requests.get(
                f"{GRAPH_API}/{container_id}",
                params={"fields": "status_code", "access_token": ACCESS_TOKEN},
                timeout=15,
            )
            status = resp.json().get("status_code", "")
            if status == "FINISHED":
                return self._publish_container(container_id)
            if status == "ERROR":
                log.error(f"Processamento de vídeo falhou: {resp.json()}")
                return False
            log.info(f"Aguardando processamento de vídeo ({status})...")
            time.sleep(15)
            waited += 15
        log.error("Timeout aguardando processamento de vídeo")
        return False

    def _upload_image(self, image_path: str) -> str | None:
        """
        A Graph API requer URL pública para imagens.
        Tenta imgbb (primário) → freeimage.host (fallback).
        """
        import base64
        with open(image_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode("utf-8")

        # Primário: imgbb
        for attempt in range(1, 3):
            try:
                resp = requests.post(
                    "https://api.imgbb.com/1/upload",
                    data={"key": os.getenv("IMGBB_API_KEY", ""), "image": img_data},
                    timeout=30,
                )
                data = resp.json()
                if data.get("success"):
                    url = data["data"]["url"]
                    log.info(f"Imagem uploaded (imgbb): {url}")
                    return url
                log.warning(f"imgbb tentativa {attempt}/2: {data}")
            except Exception as e:
                log.warning(f"imgbb tentativa {attempt}/2 erro: {e}")
            time.sleep(5)

        # Fallback: Imgur (anonymous, sem auth, aceito pelo Meta)
        try:
            import base64 as _b64
            with open(image_path, "rb") as f:
                img_b64 = _b64.b64encode(f.read()).decode()
            resp = requests.post(
                "https://api.imgur.com/3/upload",
                headers={"Authorization": "Client-ID f0ea04148a54268"},
                data={"image": img_b64, "type": "base64"},
                timeout=30,
            )
            data = resp.json()
            if data.get("success"):
                url = data["data"]["link"]
                log.info(f"Imagem uploaded (imgur): {url}")
                return url
            log.error(f"imgur falhou: {data}")
        except Exception as e:
            log.error(f"imgur erro: {e}")

        log.error(f"Upload de imagem falhou em todos os hosts: {image_path}")
        return None

    def _upload_video(self, video_path: str) -> str | None:
        """Upload via catbox.moe (gratuito, sem auth, 72h expiry — suficiente para o Meta processar)."""
        try:
            with open(video_path, "rb") as f:
                resp = requests.post(
                    "https://catbox.moe/user/api.php",
                    data={"reqtype": "fileupload"},
                    files={"fileToUpload": (Path(video_path).name, f, "video/mp4")},
                    timeout=120,
                )
            url = resp.text.strip()
            if url.startswith("https://"):
                log.info(f"Vídeo uploaded (catbox): {url}")
                return url
            log.error(f"catbox retornou: {url}")
        except Exception as e:
            log.error(f"Upload de vídeo falhou: {e}")
        return None

    def _build_caption(self, caption: str, hashtags: list[str] = None) -> str:
        if hashtags:
            tags = " ".join(f"#{h.lstrip('#')}" for h in hashtags)
            return f"{caption}\n\n{tags}"
        return caption

    def _is_configured(self) -> bool:
        if not ACCESS_TOKEN or not IG_USER_ID:
            log.error("Meta Graph API não configurada — preencha META_ACCESS_TOKEN e META_IG_USER_ID no .env")
            return False
        return True
