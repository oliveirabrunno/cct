"""
Pipeline de stories autônomo com frequência própria.
Gera stories standalone a partir de notícias, ranking e contexto de torneio.
Tipos: news_update, tournament_stat, trending_fact, draw_teaser.
"""

import asyncio
import time
from pathlib import Path
from generators.story import StoryGenerator
from generators.content import ContentGenerator
from utils.logger import get_logger

log = get_logger(__name__)

OUTPUT_DIR = Path("output/queue")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


_STALE_KEYWORDS = [
    "relembre", "relembra", "história", "lenda", "aniversário", "anos atrás",
    "os melhores", "top 10", "ranking dos", "galeria", "arquivo",
    "remember when", "on this day", "throwback", "classic",
]

_BREAKING_KEYWORDS = [
    "vence", "venceu", "derrota", "derrotou", "avança", "avançou",
    "elimina", "eliminou", "conquista", "conquistou", "anuncia",
    "lesão", "lesionado", "retira", "retirou", "semifinal", "final",
    "beats", "defeated", "advances", "wins", "announces", "injured",
    "withdraws", "semifinal", "quarterfinal",
]


def _is_relevant_news(article: dict) -> bool:
    """Retorna True apenas para notícias de fatos acontecendo agora."""
    text = (article.get("title", "") + " " + article.get("summary", "")).lower()
    if any(kw in text for kw in _STALE_KEYWORDS):
        return False
    return any(kw in text for kw in _BREAKING_KEYWORDS)


async def _generate_news_story(gen: StoryGenerator, content_gen: ContentGenerator) -> str | None:
    """Story de novidade: puxa notícia quente e gera curiosity story."""
    try:
        from scrapers.google_news import fetch_recent_news
        news = fetch_recent_news(hours=3)
        if not news:
            return None

        # Filtrar apenas notícias com fatos acontecendo agora
        relevant = [a for a in news if _is_relevant_news(a)]
        if not relevant:
            log.info("news_story: nenhuma notícia relevante/breaking nas últimas 3h — pulando story")
            return None

        top = relevant[0]
        headline = top.get("title", "")
        summary  = top.get("summary", top.get("description", ""))[:200]
        player   = top.get("player", "")

        # Pedir ao Claude um stat/curiosidade extraído da notícia
        prompt = (
            f"A partir dessa notícia de tênis, extraia 1 stat impactante e curto (máx 8 palavras) "
            f"e 1 contexto (máx 20 palavras).\n"
            f"Notícia: {headline}\nResumo: {summary}\n"
            f"Responda em JSON: {{\"stat\": \"\", \"context\": \"\", \"player\": \"\"}}"
        )
        from generators.content import _load_prompt
        system = _load_prompt("base_voice")
        raw = content_gen._call_claude(system, prompt, max_tokens=512)
        data = content_gen._parse_json_response(raw)

        stat    = data.get("stat", headline[:50])
        context = data.get("context", summary[:80])
        player  = data.get("player", player)

        return await gen.generate_curiosity_story(stat, context, player_name=player)
    except Exception as e:
        log.error(f"news_story falhou: {e}")
        return None


async def _generate_tournament_story(gen: StoryGenerator, content_gen: ContentGenerator) -> str | None:
    """Story de contexto do torneio: surface, data, quem defender título."""
    try:
        from scrapers.tournament_draw import CURRENT_TOURNAMENT, get_tournament_seeds
        t = CURRENT_TOURNAMENT
        seeds = get_tournament_seeds("atp")
        seed1 = seeds[0]["name"] if seeds else "o #1 do mundo"

        stat    = f"{t['short'].upper()} começa {t['date'].split('–')[0].strip()}"
        context = (
            f"{t['category']} em {t['location']}. "
            f"Superfície: {t['surface']}. "
            f"{seed1} é o grande favorito."
        )
        return await gen.generate_curiosity_story(stat, context)
    except Exception as e:
        log.error(f"tournament_story falhou: {e}")
        return None


async def _generate_ranking_story(gen: StoryGenerator) -> str | None:
    """Story de ranking brasileiro com copy gerado pelo Claude — ângulo variado a cada publicação."""
    try:
        from scrapers.live_ranking import fetch_atp_live_rankings, fetch_wta_live_rankings
        from generators.content import ContentGenerator, _load_prompt
        from utils.dedup import player_posted_recently

        atp = fetch_atp_live_rankings(30)
        wta = fetch_wta_live_rankings(30)

        bra_atp = next((p for p in atp if p["country"] == "BRA"), None)
        bra_wta = next((p for p in wta if p["country"] == "BRA"), None)

        # Escolher jogador — respeitar cooldown para não saturar Fonseca
        if bra_atp and not player_posted_recently("João Fonseca", hours=22):
            player_name = "João Fonseca"
            rank   = bra_atp["rank"]
            points = bra_atp["points"]
        elif bra_wta and not player_posted_recently("Beatriz Haddad Maia", hours=22):
            player_name = "Beatriz Haddad Maia"
            rank   = bra_wta["rank"]
            points = bra_wta["points"]
        else:
            log.info("ranking_story: jogadores brasileiros em cooldown — pulando")
            return None

        # Claude gera copy com ângulo novo — não apenas "X #N no mundo"
        content_gen = ContentGenerator()
        system = _load_prompt("base_voice")
        prompt = (
            f"Gere conteúdo para um story Instagram sobre {player_name}, tenista brasileiro.\n"
            f"Dados: #{rank} no ranking mundial, {points} pontos.\n\n"
            f"REGRAS DE COPY:\n"
            f"- badge: rótulo curto, máx 12 chars (ex: RANKING, ATP LIVE, DESTAQUE BR, TOP {rank})\n"
            f"- kicker: contexto de torneio/período, máx 38 chars (ex: Roland Garros · Fase de Grupos)\n"
            f"- title: frase de impacto, máx 28 chars\n"
            f"  VARIAR O ÂNGULO — nunca repetir o mesmo estilo:\n"
            f"  conquista recente | trajetória de evolução | rivalidade | dado histórico | momento atual\n"
            f"  Exemplos válidos: 'Brasil tem seu herói', 'Ascensão imparável', 'Top {rank} confirmado',\n"
            f"  'Melhor fase da carreira', 'O momento é agora'\n"
            f"  PROIBIDO: 'melhor desde Guga', 'mais bem ranqueado desde', 'o brasileiro mais...'\n"
            f"- subtitle: 1 frase de contexto rico, máx 85 chars, com dado concreto\n\n"
            f"Responda JSON: {{\"badge\":\"\", \"kicker\":\"\", \"title\":\"\", \"subtitle\":\"\"}}"
        )
        raw  = content_gen._call_claude(system, prompt, max_tokens=300)
        data = content_gen._parse_json_response(raw)
        if not data:
            return None

        return await gen.generate_curiosity_story(
            stat=data.get("title", f"#{rank} no mundo"),
            context=data.get("subtitle", f"{points} pontos ATP"),
            player_name=player_name,
            surface="clay",
            badge=data.get("badge", "RANKING"),
            kicker=data.get("kicker", f"#{rank} · {points} pts"),
        )
    except Exception as e:
        log.error(f"ranking_story falhou: {e}")
        return None


async def _generate_draw_teaser_story(gen: StoryGenerator) -> str | None:
    """Story de teaser apontando para o carrossel de draw path."""
    try:
        from scrapers.tournament_draw import CURRENT_TOURNAMENT, get_tournament_seeds
        t = CURRENT_TOURNAMENT
        seeds_atp = get_tournament_seeds("atp")
        seed1 = seeds_atp[0]["name"].split()[-1] if seeds_atp else "Sinner"

        stat    = f"Quem chega na final de {t['short']}?"
        context = (
            f"Fizemos o caminho completo de todos os favoritos. "
            f"Veja no carrossel. @cafecomteniss"
        )
        return await gen.generate_curiosity_story(stat, context)
    except Exception as e:
        log.error(f"draw_teaser_story falhou: {e}")
        return None


STORY_TYPES = [
    ("news_update",      _generate_news_story),
    ("ranking_update",   _generate_ranking_story),
    ("tournament_info",  _generate_tournament_story),
    ("draw_teaser",      _generate_draw_teaser_story),
]


async def run_story_feed(count: int = 3, publish: bool = True) -> list[str]:
    """
    Gera `count` stories standalone variados.
    Roda a cada 3-4h via crontab — mantém a conta ativa entre posts.
    """
    gen         = StoryGenerator()
    content_gen = ContentGenerator()

    if publish:
        try:
            import os, requests as req
            token   = os.getenv("META_ACCESS_TOKEN", "")
            page_id = os.getenv("PAGE_ID", "")
            if token and page_id:
                resp = req.get(
                    f"https://graph.facebook.com/v19.0/{page_id}",
                    params={"fields": "instagram_business_account", "access_token": token},
                    timeout=5,
                ).json()
                if resp.get("instagram_business_account"):
                    from publisher.graph_publisher import GraphPublisher
                    publisher = GraphPublisher()
                else:
                    from publisher.local_publisher import LocalPublisher
                    publisher = LocalPublisher()
            else:
                from publisher.local_publisher import LocalPublisher
                publisher = LocalPublisher()
        except Exception:
            from publisher.local_publisher import LocalPublisher
            publisher = LocalPublisher()
    else:
        from publisher.local_publisher import LocalPublisher
        publisher = LocalPublisher()

    from utils.dedup import is_duplicate, register_post
    from datetime import date

    # TTLs por tipo: news pode repetir a cada 3h (notícia diferente);
    # conteúdo estático (ranking, torneio, draw) uma vez por dia.
    STORY_TTL = {
        "news_update":     3,   # horas — notícia diferente a cada vez
        "ranking_update":  48,  # a cada 2 dias — Claude varia o ângulo mas conteúdo é similar
        "tournament_info": 24,
        "draw_teaser":     24,
    }

    today = date.today().isoformat()

    published = []
    for i, (story_type, generator_fn) in enumerate(STORY_TYPES[:count]):
        ttl = STORY_TTL.get(story_type, 4)
        dedup_key = f"{story_type}_{today}"

        if is_duplicate(f"story_{story_type}", dedup_key, hours=ttl):
            log.info(f"Story {story_type} já publicado nas últimas {ttl}h — pulando")
            continue

        log.info(f"Gerando story #{i+1}: {story_type}")
        try:
            if story_type in ("news_update", "tournament_info"):
                path = await generator_fn(gen, content_gen)
            else:
                path = await generator_fn(gen)

            if path:
                await publisher.publish_story(path)
                register_post(f"story_{story_type}", dedup_key)
                published.append(path)
                log.info(f"Story publicado: {story_type} → {path}")
            else:
                log.warning(f"Story {story_type} não gerou imagem")
        except Exception as e:
            log.error(f"Story {story_type} falhou: {e}")

        if i < count - 1:
            await asyncio.sleep(1)

    log.info(f"Story feed: {len(published)}/{count} publicados")
    return published


if __name__ == "__main__":
    asyncio.run(run_story_feed(count=2, publish=False))
