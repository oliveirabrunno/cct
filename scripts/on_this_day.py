"""
Gera card "Hoje na História do Tênis" + story teaser.
Fonte primária: banco Sackmann (atp_matches / wta_matches CSVs).
Fonte fallback: Claude API gera um fato histórico relevante para o dia.

Publicado às 06:00 BRT via on_this_day.yml GitHub Action.
"""

import asyncio
import csv
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from utils.logger import get_logger

log = get_logger(__name__)

RELEVANT_ROUNDS = {"F", "SF"}
PREMIUM_TOURNAMENTS = {
    "Roland Garros", "Wimbledon", "US Open", "Australian Open",
    "Rome", "Madrid", "Indian Wells", "Miami", "Paris",
    "Monte Carlo", "Canadian Open", "Cincinnati", "Hamburg",
    "Qatar Open", "Dubai", "Acapulco",
}


def _months_pt(month: int) -> str:
    months = [
        "", "janeiro", "fevereiro", "março", "abril", "maio", "junho",
        "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"
    ]
    return months[month]


def get_historical_matches(today: date) -> list[dict]:
    """Busca partidas históricas neste dia (mês/dia) nos CSVs Sackmann."""
    month_day = today.strftime("%m%d")
    results = []

    for data_dir, tour_label in [
        (Path("data/sackmann/tennis_atp"), "ATP"),
        (Path("data/sackmann/tennis_wta"), "WTA"),
    ]:
        if not data_dir.exists():
            continue

        match_files = sorted(
            list(data_dir.glob("*_matches_????.csv")),
            key=lambda f: f.stem[-4:],
            reverse=True,
        )

        for csv_file in match_files[:25]:
            try:
                with open(csv_file, "r", encoding="utf-8", errors="replace") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        td = str(row.get("tourney_date", ""))
                        if len(td) < 8 or td[4:8] != month_day:
                            continue

                        round_name = row.get("round", "")
                        tournament = row.get("tourney_name", "")

                        if round_name not in RELEVANT_ROUNDS:
                            continue
                        if tournament not in PREMIUM_TOURNAMENTS:
                            continue

                        results.append({
                            "year": td[:4],
                            "winner": row.get("winner_name", ""),
                            "loser": row.get("loser_name", ""),
                            "score": row.get("score", ""),
                            "tournament": tournament,
                            "round": round_name,
                            "surface": row.get("surface", ""),
                            "tour": tour_label,
                        })
            except Exception as e:
                log.debug(f"Erro ao ler {csv_file}: {e}")
                continue

    # Priorizar: finals > semis, depois anos mais recentes
    priority = {"F": 2, "SF": 1}
    results.sort(key=lambda x: (priority.get(x["round"], 0), x["year"]), reverse=True)

    return results[:5]


async def run():
    from generators.content import ContentGenerator, _load_prompt
    from generators.visual import generate_card_with_player
    from generators.story import StoryGenerator
    from publisher.rate_limiter import can_publish_feed_post
    from utils.dedup import is_duplicate, register_post

    today = date.today()

    if is_duplicate("on_this_day", today.isoformat(), hours=20):
        log.info("On This Day já publicado hoje — pulando")
        return

    matches = get_historical_matches(today)
    content_gen = ContentGenerator()
    system = _load_prompt("base_voice")

    day_str = f"{today.day} de {_months_pt(today.month)}"

    if matches:
        m = matches[0]
        years_ago = today.year - int(m["year"])
        round_label = "final" if m["round"] == "F" else "semifinal"
        prompt = (
            f"Hoje, {day_str}. Há {years_ago} anos (em {m['year']}), "
            f"{m['winner']} venceu {m['loser']} ({m['score']}) na {round_label} de {m['tournament']} ({m['tour']}).\n\n"
            "Gere um card 'Hoje na história do tênis' viral para Instagram.\n"
            "REGRAS:\n"
            "- headline: o dado mais impactante, máx 8 palavras, sem introdução\n"
            "- subtext: contexto histórico, máx 20 palavras\n"
            "- player: nome completo do jogador principal\n"
            "- caption: legenda (máx 80 palavras), tom de bar, CTA invisível no final\n"
            "Responda SOMENTE JSON: {\"headline\":\"\",\"subtext\":\"\",\"player\":\"\",\"caption\":\"\"}"
        )
        log.info(f"Fato encontrado: {m['year']} {m['winner']} def {m['loser']} em {m['tournament']}")
    else:
        prompt = (
            f"Hoje é {day_str}. Gere um fato histórico marcante do tênis para essa data.\n"
            "Pode ser um recorde quebrado, conquista histórica, ou momento icônico real.\n"
            "REGRAS:\n"
            "- headline: máx 8 palavras, impactante, sem introdução\n"
            "- subtext: contexto, máx 20 palavras\n"
            "- player: jogador principal (ou vazio se for sobre o esporte em geral)\n"
            "- caption: legenda (máx 80 palavras), tom de bar, CTA invisível\n"
            "Responda SOMENTE JSON: {\"headline\":\"\",\"subtext\":\"\",\"player\":\"\",\"caption\":\"\"}"
        )
        log.info("Sem dados Sackmann — usando Claude para gerar fato histórico")

    raw = content_gen._call_claude(system, prompt, max_tokens=400)
    data = content_gen._parse_json_response(raw)

    headline = data.get("headline", f"Hoje na história. {today.strftime('%d/%m')}.")
    subtext = data.get("subtext", "")
    player = data.get("player", "")
    caption = data.get("caption", headline)

    hashtags = [
        "#tennis", "#tenis", "#onthisday", "#historiadotenis", "#hoje",
        "#ATP", "#WTA", "#cafecomtenis", "#cafecomteniss",
    ]
    if player:
        last_name = player.split()[-1].lower().replace("-", "")
        hashtags.append(f"#{last_name}")

    card_data = {
        "player": player,
        "tournament": f"Hoje na História · {today.strftime('%d/%m')}",
    }
    content_data = {
        "headline": headline,
        "subtext": subtext,
        "visual_note": "foto_clean",
    }

    path = await generate_card_with_player("stat_card", card_data, content_data)

    if not path:
        log.error("Falha ao gerar card On This Day")
        return

    if not can_publish_feed_post():
        log.warning("Quota Meta atingida — card salvo localmente")
        return

    try:
        from publisher.graph_publisher import GraphPublisher
        publisher = GraphPublisher()

        ok = await publisher.publish_post(str(path), caption, hashtags)
        if ok:
            register_post("on_this_day", today.isoformat(), description=headline)
            log.info(f"On This Day publicado: {headline}")

        if not is_duplicate("story_on_this_day", today.isoformat(), hours=20):
            story_gen = StoryGenerator()
            story_path = await story_gen.generate_curiosity_story(
                stat=headline,
                context=subtext or "Veja o post 👆",
                player_name=player,
            )
            if story_path:
                await publisher.publish_story(story_path)
                register_post("story_on_this_day", today.isoformat())
                log.info("Story teaser On This Day publicado")

    except Exception as e:
        log.error(f"Publicação On This Day falhou: {e}")


if __name__ == "__main__":
    asyncio.run(run())
