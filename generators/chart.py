"""
Gerador de gráficos para insights de dados (ATP IQ).
Utiliza Matplotlib para gerar imagens minimalistas no formato de cores da marca.
"""

import os
import time
from pathlib import Path
from utils.logger import get_logger

log = get_logger(__name__)

# Definindo cores da marca
BG_COLOR = "#0A0A0A"
ACCENT_COLOR = "#C8F135"
TEXT_COLOR = "#FFFFFF"
GRID_COLOR = "#333333"

OUTPUT_DIR = Path("output/queue")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def generate_bar_chart(title: str, labels: list[str], values: list[float], output_path: str = None) -> str:
    """Gera um gráfico de barras horizontal minimalista."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        log.error("Matplotlib não está instalado.")
        return ""

    if not output_path:
        ts = int(time.time())
        output_path = str(OUTPUT_DIR / f"chart_bar_{ts}.png")

    fig, ax = plt.subplots(figsize=(10, 8), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    y_pos = np.arange(len(labels))
    bars = ax.barh(y_pos, values, color=ACCENT_COLOR, height=0.5)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, color=TEXT_COLOR, fontsize=18, fontweight='bold')
    ax.invert_yaxis()  # top-to-bottom

    ax.xaxis.grid(True, color=GRID_COLOR, linestyle='--', linewidth=0.5)
    ax.set_axisbelow(True)
    
    # Remover bordas
    for spine in ['top', 'right', 'bottom', 'left']:
        ax.spines[spine].set_visible(False)
        
    ax.tick_params(axis='x', colors=TEXT_COLOR, labelsize=14)
    ax.tick_params(axis='y', left=False)

    plt.title(title.upper(), color=TEXT_COLOR, fontsize=24, pad=20, fontweight='bold', loc='left')

    plt.tight_layout()
    plt.savefig(output_path, dpi=120, facecolor=BG_COLOR, bbox_inches='tight')
    plt.close()

    log.info(f"Gráfico gerado: {output_path}")
    return output_path

def generate_radar_chart(player: str, categories: list[str], values: list[float], output_path: str = None) -> str:
    """Gera um gráfico de radar (teia de aranha) para DNA do jogador."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        log.error("Matplotlib não está instalado.")
        return ""

    if not output_path:
        ts = int(time.time())
        output_path = str(OUTPUT_DIR / f"chart_radar_{ts}.png")

    # Número de variáveis
    N = len(categories)

    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]
    
    values = values + values[:1]

    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(polar=True), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    plt.xticks(angles[:-1], categories, color=TEXT_COLOR, size=16, fontweight='bold')
    
    ax.tick_params(axis='y', colors=TEXT_COLOR, labelsize=12)
    ax.set_rlabel_position(0)
    plt.yticks([2, 4, 6, 8], ["2", "4", "6", "8"], color=GRID_COLOR, size=10)
    plt.ylim(0, 10)

    # Cores de grade
    ax.grid(color=GRID_COLOR, linestyle='--', linewidth=1)
    ax.spines['polar'].set_color(GRID_COLOR)

    ax.plot(angles, values, linewidth=3, linestyle='solid', color=ACCENT_COLOR)
    ax.fill(angles, values, color=ACCENT_COLOR, alpha=0.25)

    plt.title(f"DNA: {player.upper()}", color=TEXT_COLOR, fontsize=24, pad=40, fontweight='bold')

    plt.tight_layout()
    plt.savefig(output_path, dpi=120, facecolor=BG_COLOR, bbox_inches='tight')
    plt.close()

    log.info(f"Radar chart gerado: {output_path}")
    return output_path
