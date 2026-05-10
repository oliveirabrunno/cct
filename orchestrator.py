"""
Café com Tênis — Orchestrador principal.

Modos de execução:
  python orchestrator.py daily          # pipeline diário completo (09:00 BRT)
  python orchestrator.py on-this-day    # card histórico do dia (06:00 BRT)
  python orchestrator.py stat-card      # stat chocante do player trending (10:30 BRT)
  python orchestrator.py night-recap    # reel recap do dia (21:00 BRT)
  python orchestrator.py trends         # verifica atletas em trend agora
  python orchestrator.py live           # checa scores ao vivo e gera breaking news
  python orchestrator.py ranking        # gera post de ranking semanal
  python orchestrator.py draw-path      # 1 carrossel ATP + 1 WTA (top 4 seeds + brasileiros)
  python orchestrator.py draw-path sinner          # carrossel individual só para Sinner
  python orchestrator.py draw-path fonseca         # carrossel individual só para Fonseca
  python orchestrator.py stories       # gera e publica 3 stories autônomos agora
  python orchestrator.py rg-launch      # pacote de lançamento Roland Garros
  python orchestrator.py test-card      # gera card de teste (João Fonseca)
  python orchestrator.py test-carousel  # gera carrossel de trend de teste
  python orchestrator.py test-story     # gera stories de teste
  python orchestrator.py test-tts       # testa geração de áudio
  python orchestrator.py test-reel      # gera reel de teste
  python orchestrator.py test-draw      # testa draw path sem publicar
  python orchestrator.py test-match     # testa card de resultado (Popyrin x Berrettini)
  python orchestrator.py calendar       # calendário editorial (próximos 14 dias)
  python orchestrator.py check-meta     # diagnóstico integração Instagram
"""

import asyncio
import sys
from dotenv import load_dotenv

load_dotenv()

from scrapers.google_news import fetch_recent_news, search_news
from scrapers.tournament_draw import CURRENT_TOURNAMENT
CURRENT_TOURNAMENT_SHORT = CURRENT_TOURNAMENT.get("name", "ATP Tour")
from scrapers.reddit_tennis import fetch_hot_posts
from analytics.trend_detector import TrendDetector
from generators.content import ContentGenerator
from generators.carousel import generate_trend_carousel
from generators.visual import generate_card_with_player
from generators.story import StoryGenerator
from generators.tts import generate_tts
from generators.reel import generate_reel_from_carousel, generate_quick_reel
from publisher.local_publisher import LocalPublisher
from utils.dedup import is_duplicate, register_post
from utils.logger import get_logger

log = get_logger("orchestrator")


def _make_publisher():
    """Retorna GraphPublisher se as variáveis Meta estiverem configuradas, senão LocalPublisher."""
    import os
    token = os.getenv("META_ACCESS_TOKEN", "")
    ig_user_id = os.getenv("META_IG_USER_ID", "")
    if token and ig_user_id:
        from publisher.graph_publisher import GraphPublisher
        log.info(f"Publisher: Meta Graph API (IG user {ig_user_id})")
        return GraphPublisher()
    log.info("Publisher: local (META_ACCESS_TOKEN ou META_IG_USER_ID não configurados)")
    return LocalPublisher()


async def run_daily_pipeline():
    log.info("=== Pipeline diário iniciado ===")

    # Atualiza rankings em tempo real antes de gerar qualquer conteúdo
    try:
        from scripts.update_facts import update_facts
        update_facts()
    except Exception as e:
        log.warning(f"update_facts falhou (não crítico): {e}")

    detector = TrendDetector()
    publisher = _make_publisher()
    story_gen = StoryGenerator()

    trending = await detector.check_all_players()
    log.info(f"Trending: {[t['player'] for t in trending]}")

    for trend in trending[:2]:
        player = trend["player"]
        news   = trend.get("news", [])

        if is_duplicate("trend_carousel", player):
            log.info(f"Pulando {player} — publicado recentemente")
            continue

        log.info(f"Gerando carrossel + story + reel para {player}...")
        result = await generate_trend_carousel(player, trend["signals"], news)

        if result and result.get("image_paths"):
            await publisher.publish_carousel(
                result["image_paths"], result["caption"], result["hashtags"]
            )
            register_post("trend_carousel", player, description=result["caption"][:100])

            # Story de teaser automático
            story_path = await story_gen.generate_teaser_story(
                post_data={
                    "headline": result["slides_data"][0].get("headline", ""),
                    "story_hook": result["caption"][:80],
                },
                post_type="trend_carousel",
                player_name=player,
            )
            if story_path:
                await publisher.publish_story(story_path)

            # Reel automático
            reel_path = await generate_reel_from_carousel(
                result["slides_data"], result["image_paths"], player
            )
            if reel_path:
                await publisher.publish_reel(reel_path, result["caption"], result["hashtags"])

            log.info(f"{player}: carrossel + story + reel na fila")

    if not trending:
        log.info("Sem trends — conteúdo evergreen")
        await _generate_evergreen(publisher)

    log.info("=== Pipeline diário concluído ===")


async def run_live_monitor():
    log.info("=== Monitor ao vivo ===")
    from scrapers.flashscore import check_completed_matches
    from generators.match_result_card import process_and_publish_match

    completed = await check_completed_matches()
    if not completed:
        log.info("Nenhuma partida relevante finalizada")
        return

    publisher = _make_publisher()
    story_gen = StoryGenerator()

    for match in completed:
        winner = match.get("winner", "")
        loser  = match.get("loser", "")
        score  = match.get("score", "")
        log.info(f"Resultado: {winner} def. {loser} {score}")

        # Card de resultado principal (imagem única, estilo ATP Tour)
        await process_and_publish_match(match, publisher)

        # Story de breaking news complementar (dedup por partida)
        story_key = f"breaking_{winner}_{loser}".lower().replace(" ", "_")
        if not is_duplicate("story_breaking", story_key, hours=12):
            story_path = await story_gen.generate_breaking_story(match)
            if story_path:
                await publisher.publish_story(story_path)
                register_post("story_breaking", story_key)


async def run_trend_check():
    log.info("=== Verificação de trends ===")
    detector  = TrendDetector()
    trending  = await detector.check_all_players()

    if trending:
        for t in trending:
            log.info(f"  {t['player']}: score {t['score']} | {t['signals']}")
    else:
        log.info("Nenhum atleta em trend")

    return trending


async def run_test_card():
    log.info("=== Teste: card João Fonseca ===")
    data    = {"player": "Joao Fonseca", "tournament": "Roland Garros 2026",
               "round": "Segunda rodada", "ranking": 30, "age": 19}
    content = {"headline": "FONSECA. 19 ANOS.", "visual_note": "foto_action",
                "subtext": "O brasileiro mais jovem em Roland Garros desde Guga."}

    path = await generate_card_with_player("stat_card", data, content)
    if path:
        print(f"\nCard gerado: {path}")
    else:
        print("\nERRO ao gerar card")


async def run_test_carousel():
    log.info("=== Teste: carrossel João Fonseca ===")
    news   = search_news("joao fonseca", hours=48)
    result = await generate_trend_carousel(
        "João Fonseca", {"news_count": len(news), "test": True}, news
    )

    if result and result.get("image_paths"):
        publisher = LocalPublisher()
        await publisher.publish_carousel(result["image_paths"], result["caption"], result["hashtags"])
        print(f"\n{len(result['image_paths'])} slides gerados")
        print(f"Legenda: {result['caption'][:100]}...")
    else:
        print("\nERRO ao gerar carrossel")


async def run_test_story():
    log.info("=== Teste: stories ===")
    gen = StoryGenerator()

    breaking = await gen.generate_breaking_story({
        "winner": "João Fonseca", "loser": "Carlos Alcaraz",
        "score": "7-5 6-3", "tournament": "Roland Garros 2026",
        "top_stat": "1ª vitória sobre top-3 na carreira"
    })
    print(f"Breaking story: {breaking}")

    poll = await gen.generate_h2h_poll_story(
        "João Fonseca", "Jannik Sinner",
        {"tournament": "Roland Garros", "round": "Semifinal"}
    )
    print(f"Poll story: {poll['image_path']}")

    curiosity = await gen.generate_curiosity_story(
        stat="9 brasileiros venceram Roland Garros",
        context="Guga ganhou 3. Quem será o próximo?",
        player_name="Joao Fonseca",
    )
    print(f"Curiosity story: {curiosity}")


async def run_test_tts():
    log.info("=== Teste: TTS ===")
    path = await generate_tts(
        "Fonseca. 19 anos. Cabeça de chave em Roland Garros. "
        "Um ano atrás ele disputava Challenger. Isso é história do tênis brasileiro.",
        "/tmp/tts_reel_test.mp3"
    )
    if path:
        print(f"\nÁudio gerado: {path}")
        import os
        size = os.path.getsize(path)
        print(f"Tamanho: {size/1024:.0f} KB")
    else:
        print("\nERRO ao gerar TTS")


async def run_test_reel():
    log.info("=== Teste: Reel ===")
    slides = [
        {"headline": "18 ANOS. CABEÇA DE CHAVE EM ROMA.", "subtext": "João Fonseca entra direto na segunda rodada do Masters 1000 mais tradicional do saibro."},
        {"headline": "O BRASILEIRO CHEGOU.", "subtext": "Pela primeira vez na carreira, Fonseca é cabeça de chave em Masters 1000."},
        {"headline": "O CAMINHO É PESADO.", "subtext": "Pode encarar o número 5 do mundo já na terceira rodada."},
        {"headline": "HÁ 1 ANO? OUTRO MUNDO.", "subtext": "Em 2024, Fonseca disputava Challengers. Hoje entra em Roma como protagonista."},
        {"headline": "O MAIS JOVEM TOP 60 DESDE GUGA", "subtext": "João Fonseca chega ao Masters 1000 de Roma mirando o top 30."},
        {"headline": "ATÉ ONDE VAI O JOÃO EM ROMA?", "subtext": "Comenta sua aposta. Segue cafecomteniss."},
    ]
    images = [f"output/queue/2026-05-05_19-35-53_carousel/slide_{i:02d}.png" for i in range(1, 7)]
    path = await generate_reel_from_carousel(slides, images, "João Fonseca", "trend")
    if path:
        import os
        print(f"\nReel: {path} ({os.path.getsize(path)/1024/1024:.1f} MB)")
    else:
        print("\nERRO ao gerar reel")


async def run_ranking():
    log.info("=== Ranking semanal ===")
    from datetime import date as _date
    from scrapers.live_ranking import fetch_atp_live_rankings as fetch_atp_rankings
    from scrapers.live_ranking import fetch_wta_live_rankings as fetch_wta_rankings

    if is_duplicate("ranking_carousel", str(_date.today()), hours=20):
        log.info("Ranking carousel já publicado hoje — pulando")
        return

    publisher = LocalPublisher()

    atp = fetch_atp_rankings(5)
    wta = fetch_wta_rankings(5)

    # Encontrar brasileiros no top 100
    brasileiros = {
        "atp": [p for p in fetch_atp_rankings(100) if p.get("country") in ("BRA",)],
        "wta": [p for p in fetch_wta_rankings(100) if p.get("country") in ("BRA",)],
    }

    data = {
        "atp_top10": atp,
        "wta_top10": wta,
        "brasileiros": brasileiros,
        "week": "Semana atual",
        "data": str({"atp_top5": atp, "wta_top5": wta, "brasileiros": brasileiros}),
    }

    result = await generate_trend_carousel(
        "Ranking Semanal",
        {"type": "ranking", "week": "Semana atual"},
        [],
        prompt_override=data,
        prompt_template="ranking_semanal",
    )

    if result and result.get("image_paths"):
        await publisher.publish_carousel(result["image_paths"], result["caption"], result["hashtags"])
        register_post("ranking_carousel", str(_date.today()), description=result["caption"][:100])
        print(f"Ranking gerado: {len(result['image_paths'])} slides | {result['caption'][:100]}...")


async def _generate_evergreen(publisher):
    content_gen = ContentGenerator()
    caption = content_gen.generate_caption("curiosidade_tenis", {"tema": "Roland Garros história"})
    if caption:
        log.info(f"Evergreen: {caption[:80]}...")


async def run_on_this_day():
    """Card histórico + story teaser — 06:00 BRT."""
    import subprocess
    subprocess.run([sys.executable, "scripts/on_this_day.py"])


async def run_stat_card():
    """
    Stat chocante do player mais trending — 10:30 BRT.
    Publica 1 card de feed + 1 story poll para a próxima partida.
    """
    from generators.content import ContentGenerator, _load_prompt
    from generators.visual import generate_card_with_player
    from generators.story import StoryGenerator
    from publisher.rate_limiter import can_publish_feed_post

    log.info("=== Stat Card 10:30 BRT ===")

    detector = TrendDetector()
    trending = await detector.check_all_players()

    player = trending[0]["player"] if trending else "João Fonseca"
    log.info(f"Gerando stat card para {player}")

    content_gen = ContentGenerator()
    system = _load_prompt("base_voice")

    prompt = (
        f"Gere um card de STAT CHOCANTE para {player} em {CURRENT_TOURNAMENT_SHORT}.\n"
        "REGRAS ABSOLUTAS:\n"
        "- headline: stat impactante, máx 8 palavras, SEM introdução\n"
        "- subtext: comparação histórica, máx 15 palavras\n"
        "- player_full: nome completo do jogador\n"
        "- caption: legenda Instagram (máx 70 palavras), tom de bar, CTA invisível\n"
        "Se for Fonseca/brasileiro: compare com Nadal/Alcaraz na mesma idade.\n"
        "Se for top 3 ATP/WTA: compare com pico histórico.\n"
        "Responda SOMENTE JSON: {\"headline\":\"\",\"subtext\":\"\",\"player_full\":\"\",\"caption\":\"\"}"
    )

    raw = content_gen._call_claude(system, prompt, max_tokens=350)
    data = content_gen._parse_json_response(raw)

    headline = data.get("headline", f"{player.split()[-1].upper()}.")
    subtext = data.get("subtext", "")
    caption = data.get("caption", headline)
    player_full = data.get("player_full", player)

    hashtags = [
        "#tennis", "#tenis", "#ATP", "#WTA", "#tennisstat",
        "#cafecomtenis", "#cafecomteniss",
        f"#{player_full.split()[-1].lower().replace('-', '')}",
    ]

    if is_duplicate("stat_card", player, hours=18):
        log.info(f"Stat card para {player} já publicado hoje — pulando")
        return

    path = await generate_card_with_player(
        "stat_card",
        {"player": player_full, "tournament": CURRENT_TOURNAMENT_SHORT},
        {"headline": headline, "subtext": subtext, "visual_note": "foto_action"},
    )

    if not path:
        log.warning(f"Stat card para {player_full} não gerado — foto indisponível, post abortado")
        return

    if path and can_publish_feed_post():
        publisher = _make_publisher()
        await publisher.publish_post(str(path), caption, hashtags)
        register_post("stat_card", player, description=headline)
        log.info(f"Stat card publicado: {headline}")

        story_gen = StoryGenerator()
        news = search_news(player, hours=8)
        if news and not is_duplicate("story_poll", player, hours=18):
            poll = await story_gen.generate_h2h_poll_story(
                player_full,
                "próximo adversário",
                {"tournament": CURRENT_TOURNAMENT_SHORT, "round": "próxima rodada"},
            )
            if poll and poll.get("image_path"):
                await publisher.publish_story(poll["image_path"])
                register_post("story_poll", player)
    elif not can_publish_feed_post():
        log.warning("Stat card: quota Meta atingida — conteúdo salvo localmente")


async def run_night_recap():
    """
    Reel de recap do dia — 21:00 BRT.
    Resume os melhores momentos e resultados das últimas 12h em 30-45 segundos.
    """
    from datetime import date as _date
    from generators.content import ContentGenerator, _load_prompt
    from generators.reel import generate_reel_from_carousel
    from generators.visual import generate_card_with_player
    from publisher.rate_limiter import can_publish_feed_post

    log.info("=== Night Recap Reel 21:00 BRT ===")

    news = search_news("tennis ATP WTA", hours=14)
    if not news:
        log.info("Night recap: sem notícias — pulando")
        return

    if is_duplicate("night_recap", str(_date.today()), hours=20):
        log.info("Night recap já publicado hoje — pulando")
        return

    content_gen = ContentGenerator()
    system = _load_prompt("base_voice")

    headlines_text = "\n".join(
        f"- {n.get('title', '')}" for n in news[:6]
    )
    prompt = (
        f"Gere um reel de recap do tênis de hoje ({_date.today().strftime('%-d/%m')}).\n"
        f"Notícias do dia:\n{headlines_text}\n\n"
        "Crie 4 slides para o reel (30-45 segundos total):\n"
        "Slide 1: Hook — o resultado mais impactante do dia. Máx 6 palavras.\n"
        "Slide 2: Contexto do resultado principal. Máx 15 palavras.\n"
        "Slide 3: Segunda notícia mais importante. Máx 15 palavras.\n"
        "Slide 4: CTA invisível — pergunta que gera debate.\n"
        "caption: legenda do reel (máx 60 palavras), tom de bar.\n"
        "player: jogador mais importante do dia.\n"
        "Responda SOMENTE JSON: {\"slides\":[{\"headline\":\"\",\"subtext\":\"\"},...],\"caption\":\"\",\"player\":\"\"}"
    )

    raw = content_gen._call_claude(system, prompt, max_tokens=500)
    data = content_gen._parse_json_response(raw)

    slides = data.get("slides", [])
    caption = data.get("caption", f"Recap do tênis — {_date.today().strftime('%-d/%m')}")
    player = data.get("player", "")

    if len(slides) < 2:
        log.info("Night recap: slides insuficientes — pulando")
        return

    # Gerar imagens de slide com PIL
    slide_images = []
    for i, slide in enumerate(slides):
        path = await generate_card_with_player(
            "stat_card",
            {"player": player, "tournament": "Recap do Dia"},
            {"headline": slide.get("headline", ""), "subtext": slide.get("subtext", ""), "visual_note": "foto_action"},
        )
        if path:
            slide_images.append(str(path))

    if len(slide_images) < 2:
        log.warning("Night recap: imagens insuficientes para reel")
        return

    reel_path = await generate_reel_from_carousel(
        slides[:len(slide_images)], slide_images, player or "recap"
    )

    hashtags = [
        "#tennis", "#tenis", "#ATP", "#WTA", "#tennisrecap",
        "#cafecomtenis", "#cafecomteniss",
        f"#{_date.today().strftime('%d%m')}",
    ]

    if reel_path and can_publish_feed_post():
        publisher = _make_publisher()
        await publisher.publish_reel(reel_path, caption, hashtags)
        register_post("night_recap", str(_date.today()), description=caption[:80])
        log.info(f"Night recap reel publicado: {caption[:60]}...")
    elif not can_publish_feed_post():
        log.warning("Night recap: quota Meta atingida")


async def run_rg_launch():
    from generators.roland_garros import run_rg_launch as _rg_launch
    await _rg_launch()


async def run_publish_match():
    """
    Publica resultado de partida específica.
    Uso: python orchestrator.py publish-match "Vencedor" "Perdedor" "6-2 6-3" "Torneio" "Rodada"
    """
    args = sys.argv[2:]
    if len(args) < 3:
        print("Uso: python orchestrator.py publish-match <vencedor> <perdedor> <score> [torneio] [rodada]")
        return

    winner     = args[0]
    loser      = args[1]
    score      = args[2]
    tournament = args[3] if len(args) > 3 else CURRENT_TOURNAMENT_SHORT
    round_name = args[4] if len(args) > 4 else ""

    from scrapers.match_stats import build_match_context
    from generators.match_result_card import generate_match_result_card
    from utils.dedup import is_duplicate, register_post

    match_key = f"{winner}_{loser}_{score}".lower().replace(" ", "_")
    if is_duplicate("match_result", match_key, hours=12):
        log.info(f"Resultado {winner} vs {loser} já publicado — pulando")
        print("Resultado já publicado recentemente.")
        return

    publisher = _make_publisher()

    log.info(f"Publicando resultado: {winner} def. {loser} {score} — {tournament} {round_name}")
    ctx = build_match_context(winner=winner, loser=loser, score=score,
                               tournament=tournament, round_name=round_name)
    result = await generate_match_result_card(ctx)
    if result:
        ok = await publisher.publish_post(result["image_path"], result["caption"], result["hashtags"])
        if ok:
            register_post("match_result", match_key, description=result["caption"][:100])
            log.info(f"Publicado: {winner} def. {loser}")
            print(f"\nCard: {result['image_path']}")
            print(f"Stat: {result['stat']}")
            print(f"Legenda: {result['caption'][:150]}...")
        else:
            print("\nERRO ao publicar — card gerado mas não postado no Instagram")
    else:
        print("\nERRO ao gerar card de resultado")


async def run_test_match_result():
    """Testa geração de card de resultado (caso Popyrin x Berrettini)."""
    log.info("=== Teste: card de resultado ===")
    from scrapers.match_stats import build_match_context
    from generators.match_result_card import generate_match_result_card

    ctx = build_match_context(
        winner="Alexei Popyrin",
        loser="Matteo Berrettini",
        score="6-2 6-3",
        tournament="Masters 1000 de Roma",
        round_name="2ª Rodada",
    )
    print(f"\nUpset detectado: {ctx['is_upset']} (diff ranking: {ctx['ranking_diff']})")
    print(f"Dominância: {ctx['dominance']} | Label: {ctx['label']}")

    result = await generate_match_result_card(ctx)
    if result:
        print(f"\nCard gerado: {result['image_path']}")
        print(f"Stat: {result['stat']}")
        print(f"Legenda: {result['caption'][:150]}...")
    else:
        print("\nERRO ao gerar card")


async def run_calendar():
    import subprocess
    subprocess.run([sys.executable, "scripts/editorial_calendar.py"])


async def run_check_meta():
    import subprocess
    subprocess.run([sys.executable, "scripts/check_meta.py"])


async def run_draw_path():
    """
    Sem argumento: 1 carrossel ATP + 1 WTA (top 4 seeds + brasileiros).
    Com argumento: carrossel individual do jogador.
    """
    from generators.draw_path import generate_tournament_overview_carousels, generate_draw_path_carousel
    from scrapers.tournament_draw import CURRENT_TOURNAMENT, get_tournament_seeds

    filter_arg = sys.argv[2].lower() if len(sys.argv) > 2 else ""

    if filter_arg:
        # Modo individual: achar o jogador nas entries confirmadas
        atp_seeds = get_tournament_seeds("atp")
        wta_seeds = get_tournament_seeds("wta")
        all_entries = [(p["name"], "atp") for p in atp_seeds] + [(p["name"], "wta") for p in wta_seeds]
        matches = [(n, t) for n, t in all_entries if filter_arg in n.lower()]

        if not matches:
            print(f"Jogador '{filter_arg}' não encontrado nas entries de {CURRENT_TOURNAMENT['short']}.")
            print("Verifique entries_atp/entries_wta em scrapers/tournament_draw.py")
            return

        publisher = _make_publisher()
        for player_name, tour in matches[:1]:
            result = await generate_draw_path_carousel(player_name, tour)
            if result and result.get("image_paths"):
                await publisher.publish_carousel(result["image_paths"], result["caption"], result["hashtags"])
                log.info(f"Publicado: {player_name}")
    else:
        # Modo padrão: 1 ATP + 1 WTA
        results = await generate_tournament_overview_carousels(publish=True)
        log.info(f"Draw overview: {len(results)} carrosséis publicados")


async def run_stories():
    """Gera e publica 3 stories autônomos (chamar a cada 3-4h)."""
    from generators.story_feed import run_story_feed
    published = await run_story_feed(count=3, publish=True)
    log.info(f"Stories publicados: {len(published)}")


async def run_test_draw():
    """Testa draw overview ATP sem publicar."""
    from generators.draw_path import generate_tournament_overview_carousel
    result = await generate_tournament_overview_carousel("atp")
    if result and result.get("image_paths"):
        print(f"\nDraw overview ATP: {result['tournament']}")
        print(f"Slides: {len(result['image_paths'])}")
        for p in result["image_paths"]:
            print(f"  {p}")
        print(f"Legenda: {result['caption'][:120]}...")
    else:
        print("\nERRO ao gerar draw overview")


async def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "help"
    modes = {
        "daily":          run_daily_pipeline,
        "on-this-day":    run_on_this_day,
        "stat-card":      run_stat_card,
        "night-recap":    run_night_recap,
        "trends":         run_trend_check,
        "live":           run_live_monitor,
        "ranking":        run_ranking,
        "draw-path":      run_draw_path,
        "stories":        run_stories,
        "rg-launch":      run_rg_launch,
        "calendar":       run_calendar,
        "check-meta":     run_check_meta,
        "test-card":      run_test_card,
        "test-carousel":  run_test_carousel,
        "test-story":     run_test_story,
        "test-tts":       run_test_tts,
        "test-reel":      run_test_reel,
        "test-draw":      run_test_draw,
        "test-match":     run_test_match_result,
        "publish-match":  run_publish_match,
    }

    if mode in modes:
        await modes[mode]()
    else:
        print(__doc__)


if __name__ == "__main__":
    asyncio.run(main())
