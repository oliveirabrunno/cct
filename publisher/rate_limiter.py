"""
Rate limiter para Meta Instagram Content Publishing API.
Verifica a quota diária antes de cada publicação no feed.

Limite Meta: 25 posts de feed por 24h (carrosséis, reels, imagens únicas).
Stories NÃO contam para esse limite.
"""

import os
import requests
from utils.logger import get_logger

log = get_logger(__name__)

GRAPH_API = "https://graph.facebook.com/v19.0"
SAFETY_BUFFER = 3  # Parar em quota_total - 3 (ex: 22/25)


def get_publishing_quota() -> dict:
    """Consulta a quota de publicação atual via Meta Graph API."""
    ig_user_id = os.getenv("META_IG_USER_ID", "")
    access_token = os.getenv("META_ACCESS_TOKEN", "")

    if not ig_user_id or not access_token:
        return {"quota_total": 25, "quota_usage": 0, "available": True, "source": "default"}

    try:
        resp = requests.get(
            f"{GRAPH_API}/{ig_user_id}/content_publishing_limit",
            params={
                "fields": "config,quota_usage",
                "access_token": access_token,
            },
            timeout=10,
        )
        data = resp.json()

        if "error" in data:
            log.warning(f"Meta API erro ao checar quota: {data['error'].get('message', data)}")
            return {"quota_total": 25, "quota_usage": 0, "available": True, "source": "error_fallback"}

        if "data" in data and data["data"]:
            item = data["data"][0]
            total = item.get("config", {}).get("quota_total", 25)
            used = item.get("quota_usage", 0)
            remaining = total - used
            return {
                "quota_total": total,
                "quota_usage": used,
                "remaining": remaining,
                "available": remaining > SAFETY_BUFFER,
                "source": "api",
            }

    except Exception as e:
        log.warning(f"Não foi possível verificar quota Meta: {e}")

    return {"quota_total": 25, "quota_usage": 0, "available": True, "source": "exception_fallback"}


def can_publish_feed_post(silent: bool = False) -> bool:
    """
    Retorna True se ainda há quota para publicar um post de feed.
    Stories não consomem quota e não precisam chamar essa função.
    """
    quota = get_publishing_quota()
    total = quota["quota_total"]
    used = quota["quota_usage"]
    remaining = total - used

    if not silent:
        log.info(f"Meta quota: {used}/{total} posts hoje ({remaining} restantes) [{quota['source']}]")

    if not quota["available"]:
        log.warning(
            f"Quota quase esgotada — {used}/{total} posts usados. "
            f"Buffer de segurança: {SAFETY_BUFFER}. Publicação pausada."
        )
        return False

    return True


def log_quota_status() -> dict:
    """Log e retorna o status atual da quota."""
    quota = get_publishing_quota()
    log.info(
        f"Status quota Meta: {quota.get('quota_usage', 0)}/{quota.get('quota_total', 25)} posts | "
        f"Restantes: {quota.get('remaining', 25)} | Disponível: {quota.get('available', True)}"
    )
    return quota
