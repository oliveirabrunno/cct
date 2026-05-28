"""
Burst orchestrator — dispara conteúdo do calendário no horário certo.

Roda a cada 30 minutos via GitHub Actions. Para cada partida em
data/upcoming_matches.json:
  - Verifica quais triggers (offset_h) estão dentro da janela atual
  - Verifica se aquele trigger já foi executado (dedup via SQLite)
  - Dispara o orchestrator no modo apropriado

Modos disparados:
  preview_carousel    → orchestrator.py match-preview "A" "B"
  stat_card           → orchestrator.py stat-card  (com player_a forçado)
  poll_story          → orchestrator.py h2h-poll
  countdown_story     → orchestrator.py stories
  result_card         → orchestrator.py live  (verifica resultado real)
  highlights_carousel → orchestrator.py trends-only

Uso:
  python scripts/burst_orchestrator.py            # checa e dispara triggers
  python scripts/burst_orchestrator.py --refresh  # atualiza calendar antes
  python scripts/burst_orchestrator.py --dry-run  # só lista o que faria
"""

import asyncio
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Permite rodar como `python scripts/burst_orchestrator.py` da raiz do projeto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from scrapers.match_calendar import (
    load_calendar, update_calendar, _load_manual_overrides
)
from utils.dedup import is_duplicate, register_post
from utils.logger import get_logger

log = get_logger(__name__)

# Janela de tolerância: trigger dispara se estamos dentro de ±30min do offset
TRIGGER_WINDOW_MINUTES = 30
# Dedup de trigger: nunca repetir o mesmo trigger pro mesmo jogo em 24h
TRIGGER_DEDUP_HOURS = 24


def _is_in_window(match_time_utc: str, offset_h: float) -> bool:
    try:
        match_dt = datetime.fromisoformat(match_time_utc)
        if match_dt.tzinfo is None:
            match_dt = match_dt.replace(tzinfo=timezone.utc)
    except Exception:
        return False
    target = match_dt + timedelta(hours=offset_h)
    now = datetime.now(timezone.utc)
    delta_min = abs((now - target).total_seconds()) / 60
    return delta_min <= TRIGGER_WINDOW_MINUTES


def _trigger_key(match_key: str, trigger_type: str) -> str:
    return f"{match_key}::{trigger_type}"


def _run_orchestrator(mode: str, args: list[str] | None = None, dry_run: bool = False) -> bool:
    cmd = [sys.executable, "orchestrator.py", mode]
    if args:
        cmd.extend(args)
    log.info(f"→ Disparando: {' '.join(cmd)}")
    if dry_run:
        return True
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=os.environ.copy())
        if result.returncode != 0:
            log.warning(f"orchestrator retornou {result.returncode}: {result.stderr[:300]}")
            return False
        return True
    except subprocess.TimeoutExpired:
        log.error(f"orchestrator timed out após 5min: {cmd}")
        return False
    except Exception as e:
        log.error(f"orchestrator falhou: {e}")
        return False


def execute_trigger(match: dict, trigger: dict, dry_run: bool = False) -> bool:
    trigger_type = trigger["type"]
    player_a = match["player_a"]
    player_b = match["player_b"]
    key = _trigger_key(match["match_key"], trigger_type)

    if is_duplicate("burst_trigger", key, hours=TRIGGER_DEDUP_HOURS, check_ig=False):
        log.debug(f"Trigger já executado: {key}")
        return False

    # Mapear tipo de trigger → modo do orchestrator
    if trigger_type == "preview_carousel":
        ok = _run_orchestrator("match-preview", [player_a, player_b], dry_run=dry_run)
    elif trigger_type == "stat_card":
        # stat-card escolhe o jogador automaticamente — vai pegar Fonseca se ele for trending
        ok = _run_orchestrator("stat-card", dry_run=dry_run)
    elif trigger_type == "poll_story":
        ok = _run_orchestrator("h2h-poll", dry_run=dry_run)
    elif trigger_type == "countdown_story":
        ok = _run_orchestrator("stories", dry_run=dry_run)
    elif trigger_type == "result_card":
        ok = _run_orchestrator("live", dry_run=dry_run)
    elif trigger_type == "highlights_carousel":
        ok = _run_orchestrator("trends-only", dry_run=dry_run)
    else:
        log.warning(f"Trigger desconhecido: {trigger_type}")
        return False

    if ok and not dry_run:
        register_post("burst_trigger", key, description=f"{trigger['label']} for {match['match_key']}")
        log.info(f"✅ Trigger executado: {trigger['label']} ({player_a} vs {player_b})")
    return ok


def run_burst_check(dry_run: bool = False) -> dict:
    # Sempre carregar o override manual também, mesmo se o calendário principal
    # estiver vazio (cache não restaurou, refresh falhou, etc.)
    matches = load_calendar()
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(hours=72)
    manual = _load_manual_overrides(now, cutoff)

    if manual:
        existing_keys = {m["match_key"] for m in matches}
        for m in manual:
            if m["match_key"] not in existing_keys:
                matches.append(m)
        log.info(f"Override manual: {len(manual)} partidas mescladas (total: {len(matches)})")

    if not matches:
        log.info("Calendário e override manual vazios — nada a disparar")
        return {"fired": 0, "candidates": 0}

    fired = 0
    candidates = 0
    for match in matches:
        for trigger in match.get("burst_plan", []):
            if _is_in_window(match["match_time_utc"], trigger["offset_h"]):
                candidates += 1
                if execute_trigger(match, trigger, dry_run=dry_run):
                    fired += 1

    log.info(f"Burst check: {fired}/{candidates} triggers disparados (dry_run={dry_run})")
    return {"fired": fired, "candidates": candidates}


async def main():
    refresh = "--refresh" in sys.argv
    dry_run = "--dry-run" in sys.argv

    if refresh or not load_calendar():
        log.info("Atualizando calendário...")
        await update_calendar()

    result = run_burst_check(dry_run=dry_run)
    if result["fired"] == 0 and result["candidates"] == 0:
        sys.exit(1)  # exit 1 = nada disparado (workflow pode pular steps subsequentes)
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
