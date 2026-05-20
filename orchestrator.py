"""
Café com Tênis — Orchestrador principal.

Modos de execução:
  python orchestrator.py daily          # pipeline diário completo (09:00 BRT)
  python orchestrator.py on-this-day    # card histórico do dia (06:00 BRT)
  python orchestrator.py stat-card      # stat chocante do player trending (10:30 BRT)
  python orchestrator.py stat-historico "Sinner" "31 vitórias consecutivas em Masters 1000"
  python orchestrator.py stat-historico "Fonseca" "Melhor ranking brasileiro desde Guga"
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

import base64
from pathlib import Path

from scrapers.google_news import fetch_recent_news, search_news
from scrapers.tournament_draw import CURRENT_TOURNAMENT
CURRENT_TOURNAMENT_SHORT = CURRENT_TOURNAMENT.get("name", "ATP Tour")
from scrapers.reddit_tennis import fetch_hot_posts
from scrapers.atp_iq import get_shocking_stat
from analytics.trend_detector import TrendDetector
from generators.content import ContentGenerator
from generators.carousel import generate_trend_carousel
from generators.visual import generate_card_with_player
from generators.story import StoryGenerator
from generators.tts import generate_tts
from generators.reel import generate_reel_from_carousel, generate_quick_reel
from publisher.local_publisher import LocalPublisher
from utils.dedup import is_duplicate, register_post, player_posted_recently
from utils.logger import get_logger
from utils.image_manager import ImageManager

log = get_logger("orchestrator")


def _image_to_base64(filepath: str) -> str:
    path = Path(filepath)
    if not path.exists():
        return ""
    ext = path.suffix.lower().strip('.')
    mime = "image/png" if ext == "png" else ("image/webp" if ext == "webp" else "image/jpeg")
    with open(path, "rb") as f:
        b64_str = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64_str}"


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

        # Gate universal: bloqueia se o jogador apareceu em QUALQUER post nas últimas 6h
        if player_posted_recently(player, hours=6):
            log.info(f"Pulando {player} — apareceu em post recente (gate universal)")
            continue
        # Dedup por tipo: bloqueia trend_carousel duplicado nas últimas 48h
        if is_duplicate("trend_carousel", player, hours=48, check_ig=True):
            log.info(f"Pulando {player} — trend_carousel publicado recentemente")
            continue

        log.info(f"Gerando carrossel + story + reel para {player}...")
        result = await generate_trend_carousel(player, trend["signals"], news)

        if result and result.get("image_paths"):
            ok = await publisher.publish_carousel(
                result["image_paths"], result["caption"], result["hashtags"]
            )
            if ok:
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
    from utils.publish_lock import acquire as lock_acquire, release as lock_release

    completed = await check_completed_matches()
    if not completed:
        log.info("Nenhuma partida relevante finalizada")
        return

    # ── Anti-duplicação: lock de publicação ──────────────────────────────────
    if not lock_acquire():
        log.warning("Outro run já está publicando — abortando para evitar duplicação.")
        return

    publisher = _make_publisher()
    story_gen = StoryGenerator()

    MAX_MATCHES_PER_RUN = 2  # Máx publicações por run — evita burst de posts
    published_count = 0

    try:
        for match in completed:
            if published_count >= MAX_MATCHES_PER_RUN:
                log.info(f"Limite de {MAX_MATCHES_PER_RUN} posts por run atingido — parando.")
                break

            winner = match.get("winner", "")
            loser  = match.get("loser", "")
            score  = match.get("score", "")
            log.info(f"Resultado: {winner} def. {loser} {score}")

            # Card de resultado principal (imagem única, estilo ATP Tour)
            ok = await process_and_publish_match(match, publisher)
            if ok:
                published_count += 1
                # Aguardar 30s entre publicações para evitar rate limit e duplicatas
                if published_count < MAX_MATCHES_PER_RUN and len(completed) > 1:
                    import asyncio as _asyncio
                    log.info("Aguardando 30s antes do próximo post...")
                    await _asyncio.sleep(30)

            # Story de breaking news complementar (dedup por partida)
            story_key = f"breaking_{winner}_{loser}".lower().replace(" ", "_")
            if not is_duplicate("story_breaking", story_key, hours=12):
                story_path = await story_gen.generate_breaking_story(match)
                if story_path:
                    await publisher.publish_story(story_path)
                    register_post("story_breaking", story_key)
    finally:
        lock_release()



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


async def run_afternoon_insight():
    """
    Insights educativos das 15h usando dados reais de tênis.
    Seleção inteligente: H2H pré-jogo → stats de saque → líderes da temporada.
    """
    from generators.content import ContentGenerator, _load_prompt
    from generators.visual import generate_post
    from scrapers.atp_iq import get_shocking_stat, get_h2h_card, get_season_leaders_card
    import re

    log.info("=== Afternoon Insight 15:00 BRT ===")

    detector = TrendDetector()
    trending = await detector.check_all_players()
    player   = trending[0]["player"] if trending else "Carlos Alcaraz"
    tournament = trending[0].get("tournament", "") if trending else ""

    # ── Seleção de tipo de post ───────────────────────────────────────────────
    # Se há dois jogadores monitorados trending → H2H pré-jogo
    stat_data = None
    post_kicker = "Dado do Dia · Café com Tênis"

    if len(trending) >= 2:
        p1 = trending[0]["player"]
        p2 = trending[1]["player"]
        try:
            h2h = get_h2h_card(p1, p2, tournament_name=tournament)
            if h2h["raw"].get("total", 0) >= 2:
                stat_data   = h2h
                post_kicker = "H2H · Dados Reais ATP"
                log.info(f"Insight: H2H {p1} vs {p2}")
        except Exception as e:
            log.debug(f"H2H falhou: {e}")

    # Fallback: stat de saque/superfície do jogador trending
    if not stat_data:
        try:
            stat_data   = get_shocking_stat(player, tournament_name=tournament)
            post_kicker = "ATP IQ · Estatística Avançada"
            log.info(f"Insight: stat card de {player}")
        except Exception as e:
            log.debug(f"get_shocking_stat falhou: {e}")

    # Fallback final: líder de BP convertidos na temporada
    if not stat_data or stat_data.get("stat_type") == "fallback":
        try:
            stat_data   = get_season_leaders_card("break-points-converted", tournament)
            post_kicker = "Temporada 2025 · Saibro"
            log.info("Insight: season leaders")
        except Exception as e:
            log.debug(f"season leaders falhou: {e}")

    if not stat_data:
        log.error("Nenhum dado disponível para o insight")
        return

    # ── Gerar legenda com Claude ─────────────────────────────────────────────
    content_gen = ContentGenerator()
    system      = _load_prompt("base_voice")

    prompt = (
        f"Crie uma legenda para o Instagram sobre este insight de tênis.\n"
        f"Headline: {stat_data['headline']}\n"
        f"Contexto: {stat_data['subtext']}\n\n"
        "REGRAS ABSOLUTAS:\n"
        "- Máx 70 palavras, tom educativo de quem entende de tênis.\n"
        "- Os dados são reais, baseados em estatísticas oficiais ATP.\n"
        "- Termine com uma pergunta para engajar.\n"
        'Responda SOMENTE JSON: {"caption":""}'
    )

    raw     = content_gen._call_claude(system, prompt, max_tokens=300)
    parsed  = content_gen._parse_json_response(raw)
    caption = parsed.get("caption", stat_data["subtext"]) if parsed else stat_data["subtext"]

    # ── Gerar visual ─────────────────────────────────────────────────────────
    post_data = {
        "surface": "neutral",
        "badge":    "INSIGHT",
        "kicker":   post_kicker,
        "title":    stat_data["headline"],
        "subtitle": stat_data["subtext"],
        "image":    _image_to_base64(stat_data["chart_path"]) if stat_data.get("chart_path") else "",
        "credit":   "Data: Sackmann ATP Dataset",
    }

    path = await generate_post("insight", {"player": player}, post_data)
    if not path:
        log.error("Falha ao gerar post do insight")
        return

    publisher = _make_publisher()
    # Gate universal: bloqueia se o jogador apareceu em QUALQUER post nas últimas 6h
    if player_posted_recently(player, hours=6):
        log.warning(f"{player} em post recente — skip insight (gate universal)")
        return
    # Dedup por tipo
    if is_duplicate("afternoon_insight", player, hours=12, check_ig=True):
        log.warning(f"{player} já apareceu num insight recente — skip")
        return

    hashtags      = re.findall(r"#\w+", caption)
    caption_clean = re.sub(r"\s*#\w+", "", caption).strip()

    ok = await publisher.publish_post(path, caption_clean, hashtags)
    if ok:
        register_post("afternoon_insight", player, description=stat_data["headline"])





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
    """
    Carrossel semanal de ranking ATP + WTA — toda segunda-feira às 09:00 BRT.
    Gera 2 slides (1 ATP, 1 WTA) com o template ranking.html:
      - Top 30 com badges de movimentação (↑↓ NEW)
      - Foto do destaque da semana
      - Resumo textual gerado por Claude
    """
    log.info("=== Ranking semanal (novo pipeline) ===")
    from datetime import date as _date
    from generators.ranking_carousel import generate_ranking_carousel
    from utils.publish_lock import acquire as lock_acquire, release as lock_release

    today_str = str(_date.today())
    if is_duplicate("ranking_carousel", today_str, hours=20):
        log.info("Ranking carousel já publicado hoje — pulando")
        return

    if not lock_acquire():
        log.warning("Publish lock ativo — abortando ranking para evitar duplicação.")
        return

    publisher = _make_publisher()

    try:
        result = await generate_ranking_carousel()

        if not result or not result.get("image_paths"):
            log.error("Ranking carousel não gerou imagens")
            return

        slides = result["image_paths"]
        caption = result["caption"]
        hashtags = result["hashtags"]

        # Resumo dos destaques no log
        m_atp = result.get("movers_atp", {})
        if m_atp.get("top_riser"):
            r = m_atp["top_riser"]
            log.info(f"Maior subida ATP: {r['name']} #{r['rank']} (+{r['change']})")
        if m_atp.get("newbies"):
            for p in m_atp["newbies"]:
                log.info(f"Estreante top 30 ATP: {p['name']} #{p['rank']} 🆕")

        ok = await publisher.publish_carousel(slides, caption, hashtags)
        if ok:
            register_post("ranking_carousel", today_str, description=caption[:100])
            log.info(f"✅ Ranking publicado: {len(slides)} slides")
        else:
            log.error("Falha ao publicar ranking no Instagram")

        print(f"\nSlides: {slides}")
        print(f"Caption: {caption[:150]}...")

    finally:
        lock_release()


async def _generate_evergreen(publisher):
    """Conteúdo evergreen quando não há trends: curiosidade histórica + story.

    Antes desta versão, apenas imprimia no log e não publicava nada — em dias
    calmos o pipeline ficava sem postar nada de relevante.
    """
    from datetime import date as _date
    from generators.content import ContentGenerator, _load_prompt
    from generators.visual import generate_card_with_player
    from generators.story import StoryGenerator
    from publisher.rate_limiter import can_publish_feed_post

    content_gen = ContentGenerator()
    system      = _load_prompt("base_voice")

    # Variar tema por dia da semana — 7 temas distintos
    EVERGREEN_THEMES = [
        ("recorde-grand-slam", "um recorde improvável de Grand Slam"),
        ("rivalidade-historica", "uma rivalidade clássica do circuito (ex: Nadal x Federer, Serena x Venus)"),
        ("zebra-historica", "uma zebra famosa em Grand Slam"),
        ("bras-no-mundo", "um feito brasileiro no tênis (Guga, Bellucci, Bia, Meligeni, etc.)"),
        ("curiosidade-superficie", "uma curiosidade técnica da superfície atual"),
        ("primeira-vez", "um momento de estreia/primeira vez histórica (primeira sul-americana, primeiro asiático, etc.)"),
        ("fato-bizarro", "um fato bizarro/inusitado do ATP/WTA Tour"),
    ]
    theme_key, theme_desc = EVERGREEN_THEMES[_date.today().weekday()]

    if is_duplicate("evergreen", theme_key, hours=24 * 8):
        log.info(f"Evergreen: tema '{theme_key}' já publicado recentemente — pulando")
        return

    prompt = (
        f"Gere um post evergreen sobre {theme_desc}.\n"
        "REGRAS ABSOLUTAS:\n"
        "- headline: máx 7 palavras, impactante.\n"
        "- subtext: contexto histórico, máx 18 palavras.\n"
        "- player: nome do jogador/atleta principal do fato (para foto).\n"
        "- caption: legenda Instagram (máx 70 palavras), tom de bar, termina com pergunta.\n"
        "- Use dados REAIS verificáveis (sem inventar números/datas).\n"
        "Responda SOMENTE JSON: {\"headline\":\"\",\"subtext\":\"\",\"player\":\"\",\"caption\":\"\"}"
    )

    raw  = content_gen._call_claude(system, prompt, max_tokens=400)
    data = content_gen._parse_json_response(raw)
    if not data or not data.get("headline"):
        log.info("Evergreen: Claude não retornou conteúdo — pulando")
        return

    headline = data["headline"]
    subtext  = data.get("subtext", "")
    player   = data.get("player", "Carlos Alcaraz")
    caption  = data.get("caption", headline)

    path = await generate_card_with_player(
        "evergreen",
        {"player": player, "tournament": CURRENT_TOURNAMENT_SHORT},
        {"headline": headline, "subtext": subtext, "visual_note": "foto_action"},
    )
    if not path:
        log.warning(f"Evergreen: card não gerado — foto indisponível para {player}")
        return

    if can_publish_feed_post():
        hashtags = ["#tennis", "#tenis", "#ATP", "#WTA", "#cafecomtenis", "#cafecomteniss", "#tennishistory"]
        ok = await publisher.publish_post(str(path), caption, hashtags)
        if ok:
            register_post("evergreen", theme_key, description=headline)
            log.info(f"Evergreen publicado [{theme_key}]: {headline}")


async def run_on_this_day():
    """Card histórico + story teaser — 06:00 BRT."""
    import subprocess
    subprocess.run([sys.executable, "scripts/on_this_day.py"])


def _get_next_opponent(player_name: str) -> str | None:
    """
    Tenta descobrir o próximo adversário real do jogador via entries do torneio.
    Retorna None se não for possível determinar (jogador lesionado, não inscrito etc.).
    """
    try:
        from scrapers.tournament_draw import CURRENT_TOURNAMENT
        entries = CURRENT_TOURNAMENT.get("entries_atp", []) + CURRENT_TOURNAMENT.get("entries_wta", [])
        name_lower = player_name.lower()
        # Verificar se o jogador está inscrito no torneio atual
        if not any(name_lower in e.lower() or e.lower() in name_lower for e in entries):
            log.info(f"_get_next_opponent: {player_name} não está inscrito em {CURRENT_TOURNAMENT['short']}")
            return None
        # Não temos dados de próxima rodada ao vivo — retornar None para não inventar
        return None
    except Exception as e:
        log.debug(f"_get_next_opponent falhou: {e}")
        return None


async def run_stat_card():
    """
    Stat chocante do player mais trending — 10:30 BRT.
    Publica 1 card de feed + 1 story poll para a próxima partida.

    Diversidade:
      - Roda jogadores: se top trending teve stat_card nas últimas 36h, pula para o próximo.
      - Varia o ângulo do stat por dia da semana (saque/RtBP/superfície/H2H/recorde/momentum/streak).
      - Dedup por (player + stat_angle) para nunca repetir o mesmo ângulo.
    """
    from generators.content import ContentGenerator, _load_prompt
    from generators.visual import generate_card_with_player
    from generators.story import StoryGenerator
    from publisher.rate_limiter import can_publish_feed_post
    from datetime import date as _date
    import hashlib

    log.info("=== Stat Card 10:30 BRT ===")

    detector = TrendDetector()
    trending = await detector.check_all_players()

    # Candidatos: trending + fallback de monitored (rotação se ninguém em trend)
    from analytics.trend_detector import MONITORED_PLAYERS
    candidates = [t["player"] for t in trending] + [
        p for p in MONITORED_PLAYERS.keys() if p not in {t["player"] for t in trending}
    ]

    # Forçar rotação: pular quem teve stat_card nas últimas 36h
    player = None
    for cand in candidates:
        if not is_duplicate("stat_card", cand, hours=36, check_ig=True):
            player = cand
            break
    if not player:
        log.info("Stat card: todos os jogadores em dedup — pulando hoje")
        return

    # Variar ângulo do stat por dia da semana (7 ângulos distintos)
    STAT_ANGLES = [
        ("saque",      "estatísticas avançadas de SAQUE (1º saque %, aces, BP salvos)"),
        ("retorno",    "estatísticas avançadas de RETORNO (% BP convertidos, vencedores no retorno)"),
        ("superficie", "domínio na superfície atual (record de vitórias em saibro/grama/dura)"),
        ("streak",     "sequência de vitórias atual ou recorde recente"),
        ("h2h",        "comparativo histórico contra rival direto da temporada"),
        ("clutch",     "performance em momentos decisivos (tie-breaks, sets longos, BP)"),
        ("temporada",  "ranking/posição na temporada (vitórias, finais, prêmio em dinheiro)"),
    ]
    angle_key, angle_desc = STAT_ANGLES[_date.today().weekday()]
    log.info(f"Stat card: {player} | ângulo: {angle_key}")

    content_gen = ContentGenerator()
    system = _load_prompt("base_voice")

    prompt = (
        f"Gere um card de STAT CHOCANTE para {player} em {CURRENT_TOURNAMENT_SHORT}.\n"
        f"ÂNGULO DO STAT (obrigatório): {angle_desc}.\n"
        "REGRAS ABSOLUTAS:\n"
        "- headline: stat impactante, máx 8 palavras, SEM introdução.\n"
        "- subtext: contexto/comparação, máx 15 palavras.\n"
        "- player_full: nome completo do jogador.\n"
        "- caption: legenda Instagram (máx 70 palavras), tom de bar, CTA invisível.\n"
        "- NÃO use comparações batidas (ex: 'mais jovem desde Nadal') — busque ângulo INÉDITO.\n"
        "- O stat DEVE ser sobre o ângulo informado, não outro.\n"
        "- Se for fim de semana (sábado/domingo): foque em recorde único da temporada.\n"
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

    publisher = _make_publisher()

    # Gate universal: bloqueia se o jogador apareceu em QUALQUER post nas últimas 4h
    if player_posted_recently(player, hours=4):
        log.info(f"Stat card para {player} bloqueado — jogador em post recente (gate universal)")
        return

    # Dedup por ângulo: bloqueia a mesma combinação (player + ângulo) nas últimas 14 dias.
    # Garante que o headline real não se repete, mesmo se o jogador aparecer várias vezes.
    headline_norm = headline.lower().strip()
    stat_signature = hashlib.sha256(f"{player}::{angle_key}::{headline_norm}".encode()).hexdigest()[:12]
    if is_duplicate("stat_card_angle", stat_signature, hours=24 * 14, check_ig=False):
        log.info(f"Stat card já publicado para {player}/{angle_key}/{headline_norm[:40]} — pulando")
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
        ok = await publisher.publish_post(str(path), caption, hashtags)
        if ok:
            register_post("stat_card", player, description=f"[{angle_key}] {headline}")
            register_post("stat_card_angle", stat_signature, description=headline)
        log.info(f"Stat card publicado: {headline}")

        story_gen = StoryGenerator()
        news = search_news(player, hours=8)
        if news and not is_duplicate("story_teaser", player, hours=18):
            # Tentar obter adversário real antes de gerar poll
            next_opponent = _get_next_opponent(player_full)
            if next_opponent:
                poll = await story_gen.generate_h2h_poll_story(
                    player_full,
                    next_opponent,
                    {"tournament": CURRENT_TOURNAMENT_SHORT, "round": "próxima rodada"},
                )
                if poll and poll.get("image_path"):
                    await publisher.publish_story(poll["image_path"])
                    register_post("story_teaser", player)
            else:
                # Sem adversário real confirmado → usar teaser story simples
                teaser = await story_gen.generate_teaser_story(
                    post_data={
                        "headline": headline,
                        "subtext":  subtext,
                        "kicker":   CURRENT_TOURNAMENT_SHORT,
                        "surface":  "clay",
                    },
                    post_type="stat_card",
                    player_name=player_full,
                )
                if teaser:
                    await publisher.publish_story(teaser)
                    register_post("story_teaser", player)
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
        ok = await publisher.publish_reel(reel_path, caption, hashtags)
        if ok:
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
    from utils.dedup import is_duplicate, register_post, player_posted_recently

    publisher = _make_publisher()

    # Gate universal
    if player_posted_recently(winner, hours=4):
        log.info(f"Resultado bloqueado — {winner} em post recente (gate universal)")
        print(f"{winner} apareceu em post recente. Use --force para forçar.")
        return

    match_key = f"{winner}_{loser}_{score}_{tournament}".lower().replace(" ", "_")
    if is_duplicate("match_result", match_key, hours=12, check_ig=True):
        log.info(f"Resultado {winner} vs {loser} já publicado — pulando")
        print("Resultado já publicado recentemente.")
        return

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


async def run_h2h_poll():
    """
    Story de H2H "Quem leva?" — engajamento.
    Escolhe dois jogadores em trend (ou top da temporada), gera poll story com
    contexto de H2H + comparativo no torneio atual. Publica como story do feed.
    """
    from generators.story import StoryGenerator
    from scrapers.atp_iq import get_h2h_card

    log.info("=== H2H Poll Story ===")
    detector = TrendDetector()
    trending = await detector.check_all_players()
    publisher = _make_publisher()
    story_gen = StoryGenerator()

    # Selecionar dois jogadores: top 2 trending, ou top trending + Fonseca/Sinner/Alcaraz
    if len(trending) >= 2:
        p1, p2 = trending[0]["player"], trending[1]["player"]
    elif len(trending) == 1:
        p1 = trending[0]["player"]
        # Fallback: pegar segundo jogador da lista de monitorados (não o p1)
        from analytics.trend_detector import MONITORED_PLAYERS
        p2 = next((p for p in MONITORED_PLAYERS if p != p1), "Carlos Alcaraz")
    else:
        log.info("H2H Poll: sem trending suficiente — pulando")
        return

    # Dedup: não repetir o mesmo par H2H em 48h
    pair_key = "::".join(sorted([p1, p2]))
    if is_duplicate("h2h_poll", pair_key, hours=48, check_ig=False):
        log.info(f"H2H poll já publicado para {p1} vs {p2} — pulando")
        return

    # Verificar se H2H tem dados reais (>= 1 confronto histórico)
    try:
        h2h_data = get_h2h_card(p1, p2, tournament_name=CURRENT_TOURNAMENT_SHORT)
        h2h_raw = h2h_data.get("raw", {})
        if h2h_raw.get("total", 0) < 1:
            log.info(f"H2H poll: {p1} vs {p2} sem confrontos — pulando")
            return
    except Exception as e:
        log.warning(f"H2H poll: get_h2h_card falhou ({p1} vs {p2}): {e}")
        return

    poll = await story_gen.generate_h2h_poll_story(
        p1, p2,
        {"tournament": CURRENT_TOURNAMENT_SHORT, "round": "Próximo confronto"},
    )
    if poll and poll.get("image_path"):
        await publisher.publish_story(poll["image_path"])
        register_post("h2h_poll", pair_key, description=f"{p1} vs {p2}")
        log.info(f"H2H poll publicado: {p1} vs {p2}")


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


async def run_stat_historico():
    """
    Gera e publica um card de estatística histórica/recorde sob demanda.

    Uso:
      python orchestrator.py stat-historico "Jogador" "Descrição do feito"

    Exemplos:
      python orchestrator.py stat-historico "Jannik Sinner" "31 vitórias consecutivas em Masters 1000"
      python orchestrator.py stat-historico "Carlos Alcaraz" "Mais jovem a vencer 3 Grand Slams diferentes"
      python orchestrator.py stat-historico "João Fonseca" "Melhor ranking brasileiro desde Guga Kuerten"
    """
    from generators.stat_historico import generate_stat_historico

    # Pegar argumentos da linha de comando
    player_name = sys.argv[2] if len(sys.argv) > 2 else None
    stat_fact   = sys.argv[3] if len(sys.argv) > 3 else None

    if not player_name or not stat_fact:
        print("\n❌ USO: python orchestrator.py stat-historico \"Jogador\" \"Fato/Recorde\"")
        print("\nExemplos:")
        print('  python orchestrator.py stat-historico "Jannik Sinner" "31 vitórias consecutivas em Masters 1000"')
        print('  python orchestrator.py stat-historico "João Fonseca" "Mais jovem brasileiro no top 30 desde Guga"')
        return

    log.info(f"=== Stat Histórica: {player_name} | {stat_fact} ===")

    result = await generate_stat_historico(player_name, stat_fact, publish=True)

    if result:
        print(f"\n✅ Card gerado: {result['image_path']}")
        print(f"   Headline: {result['headline']}")
        print(f"   Caption: {result['caption'][:120]}...")
    else:
        print("\n❌ Falha ao gerar card")


async def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "help"
    modes = {
        "daily":          run_daily_pipeline,
        "on-this-day":    run_on_this_day,
        "stat-card":      run_stat_card,
        "stat-historico":  run_stat_historico,
        "afternoon-insight": run_afternoon_insight,
        "night-recap":    run_night_recap,
        "trends":         run_trend_check,
        "live":           run_live_monitor,
        "ranking":        run_ranking,
        "draw-path":      run_draw_path,
        "stories":        run_stories,
        "h2h-poll":       run_h2h_poll,
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
