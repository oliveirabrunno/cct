#!/bin/bash
# Instala os crons do Café com Tênis.
# Uso: bash scripts/setup_crontab.sh

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNNER="$PROJECT_DIR/scripts/run_pipeline.sh"

echo "Projeto: $PROJECT_DIR"

# Lê crontab atual e remove entradas antigas do cafecomtenis
CURRENT=$(crontab -l 2>/dev/null | grep -v "cafecomtenis")

NEW_CRONS="
# cafecomtenis — atualização Sackmann (segunda 08h)
0 8 * * 1 $RUNNER update

# cafecomtenis — pipeline diário (09h)
0 9 * * * $RUNNER daily

# cafecomtenis — monitor ao vivo (a cada 3h, 6-23h)
0 6,9,12,15,18,21,23 * * * $RUNNER live

# cafecomtenis — check de trends (a cada 4h)
0 7,11,15,19 * * * $RUNNER trends

# cafecomtenis — stories autônomos (3x por dia: 10h, 14h, 19h)
0 10,14,19 * * * $RUNNER stories

# cafecomtenis — draw path torneio (início de torneio: segunda 10h30)
30 10 * * 1 $RUNNER draw-path
"

echo "$CURRENT$NEW_CRONS" | crontab -
echo "Crontab instalado. Verificando:"
crontab -l | grep cafecomtenis
