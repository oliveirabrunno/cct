"""
Publish Lock — evita publicação duplicada quando dois runs do GitHub Actions
rodam em paralelo e restauram o mesmo cache do SQLite.

Mecanismo:
  - Antes de qualquer publicação, `acquire()` cria um arquivo JSON de lock.
  - Se o lock já existir e tiver < MAX_LOCK_AGE_SECONDS, o run aborta.
  - `release()` deleta o lock ao final do run.
  - Funciona como semáforo em filesystem — funciona dentro do mesmo runner
    E entre runners diferentes que compartilham o mesmo cache persistente.
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from utils.logger import get_logger

log = get_logger(__name__)

LOCK_PATH         = Path("data/publish_lock.json")
MAX_LOCK_AGE_SEC  = 600   # 10 minutos — se o lock for mais antigo, ignora (run travado)
LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)


def acquire() -> bool:
    """
    Tenta adquirir o lock de publicação.
    Retorna True se adquirido (pode publicar), False se outro run está ativo.
    """
    run_id  = os.environ.get("GITHUB_RUN_ID", f"local-{os.getpid()}")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")

    # Verificar se já existe lock válido
    if LOCK_PATH.exists():
        try:
            existing = json.loads(LOCK_PATH.read_text())
            lock_age = time.time() - existing.get("timestamp", 0)
            lock_run = existing.get("run_id", "?")

            if lock_age < MAX_LOCK_AGE_SEC:
                log.warning(
                    f"🔒 Publish lock ativo! Run {lock_run} bloqueou há "
                    f"{int(lock_age)}s. Abortando para evitar duplicação."
                )
                return False
            else:
                log.info(f"Lock expirado ({int(lock_age)}s > {MAX_LOCK_AGE_SEC}s) — ignorando e adquirindo novo.")
        except Exception as e:
            log.debug(f"Lock inválido/corrompido, ignorando: {e}")

    # Escrever o lock
    lock_data = {
        "run_id":    run_id,
        "attempt":   attempt,
        "timestamp": time.time(),
        "acquired_at": datetime.now().isoformat(),
        "pid":       os.getpid(),
    }
    try:
        LOCK_PATH.write_text(json.dumps(lock_data, indent=2))
        log.info(f"🔓 Publish lock adquirido (run_id={run_id})")
        return True
    except Exception as e:
        log.error(f"Falha ao escrever lock: {e} — continuando sem lock")
        return True   # na dúvida, deixa publicar


def release() -> None:
    """Remove o lock ao final do run."""
    try:
        if LOCK_PATH.exists():
            LOCK_PATH.unlink()
            log.info("🔓 Publish lock liberado.")
    except Exception as e:
        log.debug(f"Erro ao liberar lock: {e}")


def lock_info() -> dict | None:
    """Retorna info do lock atual, ou None se não houver lock."""
    if not LOCK_PATH.exists():
        return None
    try:
        return json.loads(LOCK_PATH.read_text())
    except Exception:
        return None
