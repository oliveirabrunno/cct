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
    # Ranking news is not breaking news — João at #30 is old info
    "sobe no ranking", "sobe para o ranking", "atingiu o ranking",
    "subiu no ranking", "melhor ranking", "novo ranking", "ranking ao vivo",
    "ranking atp", "live ranking", "ranking mundial",
    # Injury news stays fresh for 24h max — filter after that
    "está recuperando", "continua em recuperação", "previsto para retornar",
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
        from datetime import datetime, timezone

        news = fetch_recent_news(hours=4)
        if not news:
            return None

        # Filtrar apenas notícias com fatos acontecendo agora
        relevant = [a for a in news if _is_relevant_news(a)]
        if not relevant:
            log.info("news_story: nenhuma notícia relevante/breaking nas últimas 4h — pulando story")
            return None

        # Rejeitar artigos publicados há mais de 4h (usando UTC explícito)
        now_utc = datetime.now(timezone.utc)
        fresh = []
        for a in relevant:
            try:
                pub = datetime.fromisoformat(a["published"])
                if pub.tzinfo is None:
                    pub = pub.replace(tzinfo=timezone.utc)
                age_hours = (now_utc - pub).total_seconds() / 3600
                if age_hours <= 4:
                    fresh.append(a)
                else:
                    log.debug(f"news_story: artigo descartado por idade {age_hours:.1f}h: {a['title'][:60]}")
            except Exception:
                fresh.append(a)  # sem data → incluir por precaução
        if not fresh:
            log.info("news_story: artigos relevantes são velhos demais (>4h) — pulando story")
            return None
        relevant = fresh

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

        # Guard: não gerar story de notícia se não há conteúdo real
        if not stat or len(stat.strip()) < 8:
            log.info("news_story: stat vazio ou muito curto — abortando")
            return None

        # Guard: story de notícia só sai se um feed post sobre o mesmo jogador
        # foi publicado nas últimas 2h — evita story solto sem contexto no feed
        if player:
            from utils.dedup import player_posted_recently
            if not player_posted_recently(player, hours=2):
                log.info(f"news_story: nenhum post recente sobre '{player}' no feed — pulando story")
                return None

        return await gen.generate_curiosity_story(
            stat, context,
            player_name=player,
            surface="clay",
            badge="AGORA",
            kicker=top.get("source", ""),
        )
    except Exception as e:
        log.error(f"news_story falhou: {e}")
        return None


async def _generate_tournament_story(gen: StoryGenerator, content_gen: ContentGenerator) -> str | None:
    """Story de contexto do torneio: surface, data, quem defender título."""
    try:
        from scrapers.tournament_draw import CURRENT_TOURNAMENT, get_tournament_seeds
        t = CURRENT_TOURNAMENT
        seeds = get_tournament_seeds("atp")
        seed1_name = seeds[0]["name"] if seeds else "Jannik Sinner"

        stat    = f"{t['short'].upper()} começa {t['date'].split('–')[0].strip()}"
        context = (
            f"{t['category']} em {t['location']}. "
            f"Superfície: {t['surface']}. "
            f"{seed1_name.split()[-1]} é o grande favorito."
        )
        # Passa o seed1 como player para ter foto de fundo (não renderiza branco)
        return await gen.generate_curiosity_story(
            stat, context,
            player_name=seed1_name,
            surface=t.get("surface", "clay"),
            badge=t["short"].upper(),
            kicker=t["location"],
        )
    except Exception as e:
        log.error(f"tournament_story falhou: {e}")
        return None


def _get_last_posted_rank(player_name: str) -> int | None:
    """Lê o último ranking publicado a partir do campo description no SQLite."""
    try:
        from utils.dedup import _get_conn, _normalize_string
        norm = _normalize_string(player_name)
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT description FROM posts "
                "WHERE post_type = 'story_ranking_update' AND player = ? "
                "ORDER BY published_at DESC LIMIT 1",
                (norm,)
            ).fetchone()
        if row and row[0]:
            for part in str(row[0]).split():
                if part.startswith("rank="):
                    return int(part.split("=")[1])
    except Exception:
        pass
    return None


async def _generate_ranking_story(gen: StoryGenerator) -> str | None:
    """
    Story de ranking brasileiro — dedup por nome de jogador (não por data),
    TTL de 72h. Só posta se ranking mudou ≥2 posições OU passou 5 dias desde
    a última publicação.
    """
    try:
        from scrapers.live_ranking import fetch_atp_live_rankings, fetch_wta_live_rankings
        from generators.content import ContentGenerator, _load_prompt
        from utils.dedup import is_duplicate, register_post

        atp = fetch_atp_live_rankings(30)
        wta = fetch_wta_live_rankings(30)

        bra_atp = next((p for p in atp if p["country"] == "BRA"), None)
        bra_wta = next((p for p in wta if p["country"] == "BRA"), None)

        # Dedup por NOME do jogador (persistente entre dias, independente de cache miss)
        player_name = rank = points = None

        if bra_atp and not is_duplicate("story_ranking_update", "João Fonseca", hours=72):
            player_name = "João Fonseca"
            rank   = bra_atp["rank"]
            points = bra_atp["points"]
        elif bra_wta and not is_duplicate("story_ranking_update", "Beatriz Haddad Maia", hours=72):
            player_name = "Beatriz Haddad Maia"
            rank   = bra_wta["rank"]
            points = bra_wta["points"]
        else:
            log.info("ranking_story: brasileiros em cooldown (72h) — pulando")
            return None

        # Só posta se ranking mudou ≥2 posições OU passou 5+ dias (120h)
        last_rank = _get_last_posted_rank(player_name)
        if last_rank is not None and abs(last_rank - rank) < 2:
            if is_duplicate("story_ranking_update", player_name, hours=120):
                log.info(
                    f"ranking_story: {player_name} #{rank} (último: #{last_rank}) "
                    "sem mudança significativa e postado recentemente — pulando"
                )
                return None

        content_gen = ContentGenerator()
        system = _load_prompt("base_voice")
        move = ""
        if last_rank:
            diff = last_rank - rank
            if diff > 0:
                move = f"Subiu {diff} posições desde o último post. "
            elif diff < 0:
                move = f"Caiu {abs(diff)} posições desde o último post. "

        prompt = (
            f"Gere conteúdo para um story Instagram sobre {player_name}, tenista brasileiro.\n"
            f"Dados: #{rank} no ranking mundial, {points} pontos. {move}\n\n"
            f"REGRAS DE COPY:\n"
            f"- badge: rótulo curto, máx 12 chars (ex: RANKING, ATP LIVE, DESTAQUE BR, TOP {rank})\n"
            f"- kicker: contexto de torneio/período, máx 38 chars (ex: Roland Garros · Saibro)\n"
            f"- title: frase de impacto, máx 28 chars\n"
            f"  VARIAR O ÂNGULO — nunca repetir o mesmo estilo:\n"
            f"  conquista recente | trajetória de evolução | rivalidade | dado histórico | momento atual\n"
            f"  PROIBIDO: 'melhor desde Guga', 'mais bem ranqueado desde', 'o brasileiro mais...'\n"
            f"  PROIBIDO: mencionar o número {rank} literalmente no title se não houve mudança\n"
            f"- subtitle: 1 frase de contexto rico, máx 85 chars, com dado concreto\n\n"
            f"Responda JSON: {{\"badge\":\"\", \"kicker\":\"\", \"title\":\"\", \"subtitle\":\"\"}}"
        )
        raw  = content_gen._call_claude(system, prompt, max_tokens=300)
        data = content_gen._parse_json_response(raw)
        if not data:
            return None

        path = await gen.generate_curiosity_story(
            stat=data.get("title", f"#{rank} no mundo"),
            context=data.get("subtitle", f"{points} pontos ATP"),
            player_name=player_name,
            surface="clay",
            badge=data.get("badge", "RANKING"),
            kicker=data.get("kicker", f"#{rank} · {points} pts"),
        )
        if path:
            # Registrar com nome do jogador para que player_posted_recently() funcione
            register_post("story_ranking_update", player_name, description=f"rank={rank} pts={points}")
        return path
    except Exception as e:
        log.error(f"ranking_story falhou: {e}")
        return None


async def _generate_draw_teaser_story(gen: StoryGenerator) -> str | None:
    """Story de teaser apontando para o carrossel de draw path."""
    try:
        from scrapers.tournament_draw import CURRENT_TOURNAMENT, get_tournament_seeds
        from utils.dedup import is_duplicate
        t = CURRENT_TOURNAMENT

        # Só faz teaser se o carrossel de chaveamento foi publicado nas últimas 48h
        if not is_duplicate("draw_overview", f"draw_overview_{t['short'].lower()}_atp", hours=48):
            log.info("draw_teaser: carrossel de draw não publicado ainda — pulando teaser")
            return None

        seeds_atp = get_tournament_seeds("atp")
        seed1_name = seeds_atp[0]["name"] if seeds_atp else "Jannik Sinner"
        bra_name   = next(
            (s["name"] for s in seeds_atp if s["name"] in t.get("brazilians_atp", [])),
            None
        )
        player_for_bg = bra_name or seed1_name

        stat    = f"Quem chega à final de {t['short']}?"
        context = (
            f"Fizemos o caminho completo dos favoritos. "
            f"Veja o carrossel no feed. @cafecomteniss"
        )
        return await gen.generate_curiosity_story(
            stat, context,
            player_name=player_for_bg,
            surface=t.get("surface", "clay"),
            badge="CHAVEAMENTO",
            kicker=t["short"].upper(),
        )
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

    # TTLs por tipo: news pode repetir a cada 4h (notícia diferente);
    # ranking_update gerencia seu próprio dedup internamente (por nome de jogador, não por data).
    STORY_TTL = {
        "news_update":     4,   # horas — notícia diferente a cada vez
        "tournament_info": 24,
        "draw_teaser":     24,
    }

    today = date.today().isoformat()

    published = []
    for i, (story_type, generator_fn) in enumerate(STORY_TYPES[:count]):
        # ranking_update usa dedup interno por nome de jogador (TTL 72h) —
        # não usar dedup externo por data que reseta à meia-noite e é ineficaz.
        if story_type != "ranking_update":
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
                # ranking_update registra o post dentro do próprio generator (com player name)
                if story_type != "ranking_update":
                    register_post(f"story_{story_type}", f"{story_type}_{today}")
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
