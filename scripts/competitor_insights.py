"""
Gerador de oportunidades de conteúdo baseado em monitoramento de concorrentes e trends.

Uso:
  python scripts/competitor_insights.py           # relatório de oportunidades
  python scripts/competitor_insights.py --urgent  # só urgentes (urgency=now)

Salva oportunidades em data/competitor_opportunities.json para o orchestrator usar.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from scrapers.competitor_monitor import CompetitorMonitor
from utils.dedup import is_duplicate
from utils.logger import get_logger

log = get_logger(__name__)

OUTPUT_FILE = Path("data/competitor_opportunities.json")
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)


def run_competitor_insights(urgent_only: bool = False) -> list[dict]:
    monitor = CompetitorMonitor()

    log.info("Buscando temas trending...")
    topics = monitor.get_trending_topics(hours=6)

    log.info("Buscando temas de concorrentes...")
    competitor_themes = monitor.get_competitor_themes(hours=12)

    # Combinar e pontuar
    all_opportunities = monitor.score_content_opportunity(topics)

    # Filtrar temas já publicados (usando dedup existente)
    new_opportunities = []
    for opp in all_opportunities:
        player = opp["topic"]
        # Pular se já publicamos sobre este jogador nas últimas 6h
        if is_duplicate("competitor_insight", player, hours=6, check_ig=False):
            log.debug(f"Pulando {player} — já coberto recentemente")
            continue
        new_opportunities.append(opp)

    if urgent_only:
        new_opportunities = [o for o in new_opportunities if o.get("urgency") == "now"]

    # Adicionar temas de concorrentes que não estão na lista principal
    existing_topics = {o["topic"].lower() for o in new_opportunities}
    for theme in competitor_themes[:5]:
        title = theme.get("title", "")
        if not any(t in title.lower() for t in existing_topics):
            new_opportunities.append({
                "topic": title[:60],
                "source": "competitor",
                "competitor_account": theme.get("competitor_account", ""),
                "urgency": "today",
                "content_angle": "carousel",
                "opportunity_score": 3,
                "latest_article": title,
                "latest_link": theme.get("link", ""),
                "raw_summary": title,
                "topic_slug": theme.get("link", title)[:12],
            })

    # Salvar no arquivo de saída
    output = {
        "generated_at": datetime.now().isoformat(),
        "opportunities": new_opportunities[:10],  # máx 10 por run
    }
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    log.info(f"Salvo: {len(new_opportunities)} oportunidades em {OUTPUT_FILE}")

    # Imprimir relatório
    if new_opportunities:
        print(f"\n=== {len(new_opportunities)} oportunidades de conteúdo ===")
        for i, opp in enumerate(new_opportunities[:5], 1):
            print(f"\n{i}. [{opp.get('urgency', '?').upper()}] {opp['topic']}")
            print(f"   Ângulo: {opp.get('content_angle', '?')} | Score: {opp.get('opportunity_score', 0)}")
            print(f"   {opp.get('raw_summary', '')[:100]}")
    else:
        print("\nNenhuma oportunidade nova encontrada.")

    # Exit code 0 se há urgentes (para o workflow decidir se dispara o orchestrator)
    # Exit code 1 se não há urgentes — workflow skipa o trigger_content job
    urgent = [o for o in new_opportunities if o.get("urgency") == "now"]
    if urgent:
        print(f"\n{len(urgent)} oportunidade(s) URGENTE(S) — disparar geração de conteúdo")
        sys.exit(0)

    sys.exit(1)


if __name__ == "__main__":
    urgent_only = "--urgent" in sys.argv
    run_competitor_insights(urgent_only=urgent_only)
