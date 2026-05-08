"""
Atualiza os CSVs Sackmann via git pull.
Deve rodar semanalmente (segunda-feira, antes do pipeline diário).

Uso:
    python scripts/update_sackmann.py
"""

import subprocess
import sys
from pathlib import Path

# Garante que o root do projeto está no sys.path quando executado como script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.logger import get_logger

log = get_logger(__name__)

SACKMANN_DIRS = {
    "data/sackmann/tennis_atp": "https://github.com/JeffSackmann/tennis_atp.git",
    "data/sackmann/tennis_wta": "https://github.com/JeffSackmann/tennis_wta.git",
}


def update_repo(local_path: str, remote_url: str) -> bool:
    path = Path(local_path)

    if not path.exists():
        log.info(f"Clonando {remote_url} → {path}")
        result = subprocess.run(
            ["git", "clone", "--depth=1", remote_url, str(path)],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            log.error(f"Clone falhou: {result.stderr}")
            return False
        log.info(f"Clone concluído: {path}")
        return True

    log.info(f"Atualizando {path}...")
    result = subprocess.run(
        ["git", "-C", str(path), "pull", "--ff-only"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        log.error(f"git pull falhou em {path}: {result.stderr}")
        return False

    log.info(f"{path}: {result.stdout.strip()}")
    return True


def verify_ranking_files() -> None:
    import pandas as pd
    from datetime import date

    checks = {
        "data/sackmann/tennis_atp/atp_rankings_current.csv": "ATP",
        "data/sackmann/tennis_wta/wta_rankings_current.csv": "WTA",
    }
    today = date.today()

    for csv_path, tour in checks.items():
        path = Path(csv_path)
        if not path.exists():
            log.error(f"{tour}: arquivo não encontrado — {csv_path}")
            continue

        df = pd.read_csv(path)
        latest = df["ranking_date"].max()
        log.info(f"{tour} ranking mais recente: {latest} (hoje: {today})")

        top1 = df[df["ranking_date"] == latest].sort_values("rank").iloc[0]
        log.info(f"{tour} #1: player_id={int(top1['player'])}, pts={int(top1.get('points', 0))}")


if __name__ == "__main__":
    log.info("=== Atualização Sackmann ===")
    ok = True
    for local_path, remote_url in SACKMANN_DIRS.items():
        if not update_repo(local_path, remote_url):
            ok = False

    verify_ranking_files()

    if not ok:
        log.error("Atualização com erros — verifique logs acima")
        sys.exit(1)

    log.info("=== Atualização concluída ===")
