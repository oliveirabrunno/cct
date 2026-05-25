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
        ha_x_anos = f"HÁ {years_ago} ANOS"
        prompt = (
            f"Hoje, {day_str}. Em {m['year']} (há {years_ago} anos), "
            f"{m['winner']} venceu {m['loser']} ({m['score']}) na {round_label} de {m['tournament']} ({m['tour']}).\n\n"
            "Gere um card histórico VIRAL para Instagram. O leitor deve entender IMEDIATAMENTE que é um fato do passado.\n"
            "REGRAS CRÍTICAS:\n"
            f"- headline: OBRIGATÓRIO começar com '{ha_x_anos}:' seguido do fato. Máx 10 palavras total.\n"
            f"  Exemplo correto: '{ha_x_anos}: Nadal venceu Roland Garros pela 9ª vez.'\n"
            f"  Exemplo ERRADO: 'Nadal domina Paris' (não indica que é passado)\n"
            "- subtext: contexto histórico que agrega valor, máx 20 palavras. Pode comparar com hoje.\n"
            "- caption: legenda (máx 80 palavras), tom de bar. Última frase: pergunta que gera debate.\n"
            "  Sempre deixar claro que é um fato histórico, nunca de hoje.\n"
            "Responda SOMENTE JSON: {\"headline\":\"\",\"subtext\":\"\",\"caption\":\"\"}"
        )
        log.info(f"Fato encontrado: {m['year']} {m['winner']} def {m['loser']} em {m['tournament']}")
        # SEMPRE usar o vencedor do CSV — nunca confiar no campo 'player' do Claude
        default_player = m["winner"]
        badge_label = f"Há {years_ago} Anos"
    else:
        prompt = (
            f"Hoje é {day_str}. Gere um fato histórico marcante do tênis para essa data.\n"
            "Pode ser um recorde quebrado, conquista histórica, ou momento icônico real.\n"
            "REGRAS CRÍTICAS:\n"
            "- headline: OBRIGATÓRIO começar com 'HÁ X ANOS:' (substituir X pelo número real de anos). Máx 10 palavras.\n"
            "  Exemplo: 'HÁ 15 ANOS: Federer conquistou seu 15º Grand Slam.'\n"
            "- subtext: contexto histórico, máx 20 palavras. Nunca soar como notícia atual.\n"
            "- player: jogador principal (OBRIGATÓRIO)\n"
            "- caption: legenda (máx 80 palavras), tom de bar, última frase = pergunta debate\n"
            "- years_ago: número inteiro de anos atrás (campo extra para o badge)\n"
            "Responda SOMENTE JSON: {\"headline\":\"\",\"subtext\":\"\",\"player\":\"\",\"caption\":\"\",\"years_ago\":0}"
        )
        log.info("Sem dados Sackmann — usando Claude para gerar fato histórico")
        default_player = "Roger Federer"
        badge_label = "Hoje na História"

    raw = content_gen._call_claude(system, prompt, max_tokens=400)
    data = content_gen._parse_json_response(raw)

    headline = (data.get("headline") or "").strip() or f"Há anos: história do tênis. {today.strftime('%d/%m')}."
    subtext  = (data.get("subtext") or "").strip()
    caption  = (data.get("caption") or "").strip() or headline

    # Para o caminho Sackmann: SEMPRE usar o vencedor do CSV (nunca campo 'player' do Claude)
    # Para o fallback (sem Sackmann): usar campo 'player' do Claude mas validar contra headline
    if matches:
        player = default_player  # = m["winner"] — imutável
    else:
        player = data.get("player", "").strip()
        if player:
            # Validar: sobrenome do jogador deve aparecer no headline gerado pelo Claude
            last_name = player.split()[-1].lower()
            if len(last_name) >= 3 and last_name not in headline.lower():
                log.warning(
                    f"on_this_day: jogador '{player}' ausente no headline '{headline[:60]}' "
                    f"— usando fallback '{default_player}'"
                )
                player = default_player
        player = player or default_player

    # Para o fallback sem Sackmann, extrair years_ago do response do Claude
    if not matches and data.get("years_ago"):
        badge_label = f"Há {data['years_ago']} Anos"

    hashtags = [
        "#tennis", "#tenis", "#ATP", "#WTA",
        "#cafecomtenis", "#cafecomteniss", "#tenisbrasileiro",
        "#onthisday", "#historiadotenis", "#tennishistory",
        "#rolandgarros", "#rolandgarros2026",
    ]
    if player:
        last_name = player.split()[-1].lower().replace("-", "")
        hashtags.append(f"#{last_name}")

    # Usar torneio real (do Sackmann ou vazio) para que a busca de imagem
    # receba um nome de torneio válido — nunca passar o badge_label (data label)
    # como tournament_name pois gera queries absurdas ("Isner tennis Há 16 Anos 2026")
    real_tournament = m["tournament"] if matches else ""
    card_data = {
        "player": player,
        "tournament": real_tournament,
    }
    content_data = {
        "headline": headline,
        "subtext":  subtext,
        "visual_note": "foto_clean",
    }

    log.info(f"Gerando card para: {player} | {headline}")
    path = await generate_card_with_player("stat_card", card_data, content_data)

    if not path:
        log.error(f"Card On This Day abortado para '{player}' — sem foto disponível (regra: nunca publicar sem imagem)")
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
