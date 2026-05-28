"""
Diagnóstico completo do estado do bot.

Mostra em um único run:
  - Quota Meta (rate limiter)
  - Posts recentes registrados (dedup DB)
  - Posts recentes do IG via Graph API
  - Resultado do trend detector
  - Estado do match_calendar
  - Quais workflows deveriam estar publicando AGORA

Uso (local ou Actions):
  python scripts/diagnostic.py
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from utils.logger import get_logger

log = get_logger("diagnostic")


def section(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def check_meta_quota():
    section("META RATE LIMITER")
    try:
        from publisher.rate_limiter import get_publishing_quota
        quota = get_publishing_quota()
        print(f"  quota_total:    {quota.get('quota_total')}")
        print(f"  quota_usage:    {quota.get('quota_usage')}")
        print(f"  remaining:      {quota.get('remaining', 'N/A')}")
        print(f"  available:      {quota.get('available')}")
        print(f"  source:         {quota.get('source')}")
        if not quota.get("available", True):
            print(f"  → BLOCKER: quota perto do limite (safety_buffer=3)")
    except Exception as e:
        print(f"  ERRO: {e}")


def check_dedup_db():
    section("DEDUP DB — POSTS REGISTRADOS NAS ÚLTIMAS 72H")
    try:
        from utils.dedup import get_recent_posts
        recent = get_recent_posts(hours=72)
        print(f"  Total registrado em 72h: {len(recent)}")
        if not recent:
            print("  → Nada registrado. DB vazio OU cache não restaurou.")
            return
        # Agrupar por post_type
        by_type = {}
        for r in recent:
            t = r.get("post_type", "?")
            by_type.setdefault(t, 0)
            by_type[t] += 1
        print(f"\n  Por tipo:")
        for t, n in sorted(by_type.items(), key=lambda x: -x[1]):
            print(f"    {t:30s} {n}")
        print(f"\n  Últimos 10 posts:")
        for r in recent[:10]:
            print(f"    {r['published_at'][:16]} | {r['post_type']:20s} | {r['player']:25s} | {(r.get('description') or '')[:50]}")
    except Exception as e:
        print(f"  ERRO: {e}")


def check_ig_recent_posts():
    section("INSTAGRAM GRAPH API — POSTS RECENTES NO FEED")
    try:
        from utils.dedup import _fetch_ig_recent_posts
        posts = _fetch_ig_recent_posts(limit=10)
        if not posts:
            print("  → Nenhum post retornado (token expirou? IG_USER_ID errado?)")
            return
        print(f"  {len(posts)} posts encontrados no feed")
        for p in posts:
            ts = p.get("timestamp", "")[:16]
            cap = (p.get("caption") or "")[:80].replace("\n", " ")
            print(f"    {ts} | {p.get('id', '')[:15]} | {cap}")
    except Exception as e:
        print(f"  ERRO: {e}")


async def check_trend_detector():
    section("TREND DETECTOR")
    try:
        from analytics.trend_detector import TrendDetector, MONITORED_PLAYERS, TREND_THRESHOLD, BRAZILIAN_THRESHOLD, BRAZILIAN_PLAYERS
        from scrapers.google_news import fetch_recent_news
        from scrapers.reddit_tennis import fetch_hot_posts

        # Mostrar quantidade de news/reddit
        news = fetch_recent_news(hours=6)
        try:
            reddit = fetch_hot_posts(min_score=500, max_age_hours=12)
        except Exception as e:
            print(f"  Reddit erro: {e}")
            reddit = []
        print(f"  News (últimas 6h):     {len(news)}")
        print(f"  Reddit (últimas 12h):  {len(reddit)}")
        print(f"  Threshold global:      {TREND_THRESHOLD}")
        print(f"  Threshold brasileiro:  {BRAZILIAN_THRESHOLD} (para {BRAZILIAN_PLAYERS})")

        detector = TrendDetector()
        trending = await detector.check_all_players()
        print(f"\n  Trending detectado: {len(trending)} jogadores")
        for t in trending:
            print(f"    {t['player']:25s} score={t['score']} signals={t['signals']}")

        # Mostrar score por jogador (mesmo abaixo do threshold)
        print(f"\n  Score de TODOS os jogadores (mesmo sub-threshold):")
        for player_name, terms in MONITORED_PLAYERS.items():
            score = 0
            news_count = sum(
                1 for a in news
                if any(t in (a["title_lower"] + " " + a.get("summary_lower", "")) for t in terms)
            )
            score += min(news_count, 5)
            for p in reddit:
                if any(t in p.get("title_lower", "") for t in terms):
                    score += 3
                    break
            threshold = BRAZILIAN_THRESHOLD if player_name in BRAZILIAN_PLAYERS else TREND_THRESHOLD
            flag = "✓" if score >= threshold else " "
            print(f"    {flag} {player_name:25s} score={score} (threshold={threshold}, news={news_count})")
    except Exception as e:
        import traceback
        print(f"  ERRO: {e}")
        traceback.print_exc()


def check_match_calendar():
    section("MATCH CALENDAR")
    calendar_file = Path("data/upcoming_matches.json")
    manual_file = Path("data/manual_matches.json")

    if calendar_file.exists():
        try:
            data = json.loads(calendar_file.read_text())
            matches = data.get("matches", [])
            print(f"  data/upcoming_matches.json: {len(matches)} partidas")
            print(f"  Gerado em: {data.get('generated_at', '?')}")
            for m in matches[:5]:
                print(f"    [{m.get('importance')}] {m['player_a']} vs {m['player_b']} @ {m['match_time_brt'][:16]} ({m.get('tournament', '')[:30]})")
        except Exception as e:
            print(f"  Erro lendo: {e}")
    else:
        print(f"  data/upcoming_matches.json NÃO EXISTE — match_calendar nunca rodou ou cache não restaurou")

    if manual_file.exists():
        try:
            data = json.loads(manual_file.read_text())
            matches = data.get("matches", [])
            print(f"\n  data/manual_matches.json (override): {len(matches)} partidas")
            for m in matches:
                print(f"    {m.get('player_a')} vs {m.get('player_b')} @ {m.get('match_time_brt')} (importance={m.get('importance')})")
        except Exception as e:
            print(f"  Erro lendo override: {e}")


def check_burst_triggers():
    section("BURST TRIGGERS — JANELA ATUAL")
    try:
        from scrapers.match_calendar import load_calendar
        from scripts.burst_orchestrator import _is_in_window, _trigger_key
        from utils.dedup import is_duplicate

        matches = load_calendar()
        if not matches:
            print("  Calendar vazio — nenhum trigger possível")
            return

        now_utc = datetime.now(timezone.utc)
        print(f"  Now UTC: {now_utc.isoformat()[:16]} | Now BRT: {(now_utc - timedelta(hours=3)).isoformat()[:16]}")

        for match in matches:
            print(f"\n  Match: {match['player_a']} vs {match['player_b']} @ {match['match_time_brt'][:16]} BRT")
            try:
                match_dt = datetime.fromisoformat(match["match_time_utc"])
                if match_dt.tzinfo is None:
                    match_dt = match_dt.replace(tzinfo=timezone.utc)
                hours_until = (match_dt - now_utc).total_seconds() / 3600
                print(f"    horas até o jogo: {hours_until:+.1f}h")
            except Exception:
                pass
            for trigger in match.get("burst_plan", []):
                in_window = _is_in_window(match["match_time_utc"], trigger["offset_h"])
                key = _trigger_key(match["match_key"], trigger["type"])
                already_fired = is_duplicate("burst_trigger", key, hours=24, check_ig=False)
                status = ""
                if in_window and not already_fired:
                    status = " ← DISPARARIA AGORA"
                elif in_window and already_fired:
                    status = " (já disparado)"
                elif not in_window:
                    status = " (fora da janela)"
                print(f"    {trigger['label']:30s} offset={trigger['offset_h']:+4d}h{status}")
    except Exception as e:
        import traceback
        print(f"  ERRO: {e}")
        traceback.print_exc()


def check_env_vars():
    section("VARIÁVEIS DE AMBIENTE (presença, não valor)")
    keys = [
        "ANTHROPIC_API_KEY", "META_ACCESS_TOKEN", "META_IG_USER_ID",
        "SERPAPI_KEY", "FLICKR_API_KEY", "IMGBB_API_KEY",
        "ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID", "PAGE_ID",
    ]
    for k in keys:
        v = os.environ.get(k, "")
        marker = "✓" if v else "✗"
        print(f"    {marker} {k:25s} ({'set' if v else 'MISSING'})")


async def main():
    print(f"\n[diagnostic.py] {datetime.now(timezone.utc).isoformat()}")
    check_env_vars()
    check_meta_quota()
    check_dedup_db()
    check_ig_recent_posts()
    await check_trend_detector()
    check_match_calendar()
    check_burst_triggers()
    print(f"\n{'=' * 60}")
    print("  Fim do diagnóstico")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(main())
