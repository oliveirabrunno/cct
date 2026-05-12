"""
Publica o carousel de lançamento usando containers já criados.
Roda até conseguir, com backoff.
Uso: .venv/bin/python3 scripts/publish_carousel_retry.py
"""
import os, sys, time, requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.chdir(str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from utils.logger import get_logger
log = get_logger(__name__)

TOKEN = os.getenv("META_ACCESS_TOKEN", "")
IG_ID = os.getenv("META_IG_USER_ID", "")

# Container do carrossel com todos os 8 slides prontos
CAROUSEL_ID = "18110985418717017"


def check_status(container_id: str) -> str:
    resp = requests.get(
        f"https://graph.facebook.com/v19.0/{container_id}",
        params={"fields": "status_code", "access_token": TOKEN},
        timeout=10,
    )
    return resp.json().get("status_code", "UNKNOWN")


def try_publish() -> bool:
    status = check_status(CAROUSEL_ID)
    log.info(f"Container {CAROUSEL_ID} status: {status}")

    if status not in ("FINISHED", "IN_PROGRESS"):
        log.error(f"Container não está pronto: {status}")
        return False

    resp = requests.post(
        f"https://graph.facebook.com/v19.0/{IG_ID}/media_publish",
        params={"creation_id": CAROUSEL_ID, "access_token": TOKEN},
        timeout=30,
    )
    data = resp.json()
    if "id" in data:
        log.info(f"PUBLICADO! Post ID: {data['id']}")
        return True

    err = data.get("error", {})
    log.warning(f"Falhou: [{err.get('code')}/{err.get('error_subcode')}] {err.get('message')}")
    return False


if __name__ == "__main__":
    for attempt in range(1, 6):
        log.info(f"Tentativa {attempt}/5...")
        if try_publish():
            break
        wait = 60 * attempt
        log.info(f"Aguardando {wait}s antes da próxima tentativa...")
        time.sleep(wait)
    else:
        log.error("Todas as tentativas falharam. Tente rodar novamente em 30 minutos.")
