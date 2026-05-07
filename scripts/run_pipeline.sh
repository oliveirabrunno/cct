#!/bin/bash
# Café com Tênis — runner de pipeline com log rotativo.
# Adicionar ao crontab:
#   0 8 * * 1 /path/to/cafecomtenis/scripts/run_pipeline.sh update  # segunda: atualiza Sackmann
#   0 9 * * *  /path/to/cafecomtenis/scripts/run_pipeline.sh daily   # todo dia 9h: pipeline diário
#   0 */3 * * * /path/to/cafecomtenis/scripts/run_pipeline.sh live   # a cada 3h: ao vivo
#   0 */4 * * * /path/to/cafecomtenis/scripts/run_pipeline.sh trends # a cada 4h: trends

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
LOG_DIR="$PROJECT_DIR/logs"
MODE="${1:-daily}"

mkdir -p "$LOG_DIR"

LOG_FILE="$LOG_DIR/${MODE}_$(date +%Y-%m-%d).log"

echo "=== $(date '+%Y-%m-%d %H:%M:%S') [$MODE] iniciado ===" >> "$LOG_FILE"

cd "$PROJECT_DIR"

if [ "$MODE" = "update" ]; then
    "$VENV_PYTHON" scripts/update_sackmann.py >> "$LOG_FILE" 2>&1
else
    "$VENV_PYTHON" orchestrator.py "$MODE" >> "$LOG_FILE" 2>&1
fi

echo "=== $(date '+%Y-%m-%d %H:%M:%S') [$MODE] concluído ===" >> "$LOG_FILE"

# Manter apenas os últimos 14 dias de log
find "$LOG_DIR" -name "*.log" -mtime +14 -delete
