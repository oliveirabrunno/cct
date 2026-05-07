"""
Calendário editorial do Café com Tênis.
Mostra: torneios futuros, posts agendados, fila atual, histórico recente.

Uso:
  python scripts/calendar.py           # próximos 14 dias
  python scripts/calendar.py --week    # só esta semana
  python scripts/calendar.py --queue   # apenas fila de publicação
"""

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Adicionar raiz do projeto ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Calendário de torneios ATP/WTA 2026 ───────────────────────────────────────
TOURNAMENTS_2025 = [
    # ── SAIBRO (maio-junho 2026) ──
    {"name": "Masters 1000 de Roma",    "short": "Roma",        "surface": "clay",
     "start": date(2026, 5,  4), "end": date(2026, 5, 17), "category": "M1000",
     "tours": ["ATP", "WTA"]},
    {"name": "Roland Garros",           "short": "RG",          "surface": "clay",
     "start": date(2026, 5, 24), "end": date(2026, 6,  7), "category": "Grand Slam",
     "tours": ["ATP", "WTA"]},
    # ── GRAMA (junho-julho 2026) ──
    {"name": "Queen's Club",            "short": "Queen's",     "surface": "grass",
     "start": date(2026, 6, 15), "end": date(2026, 6, 21), "category": "ATP 500",
     "tours": ["ATP"]},
    {"name": "Berlin Open",             "short": "Berlin",      "surface": "grass",
     "start": date(2026, 6, 15), "end": date(2026, 6, 21), "category": "WTA 500",
     "tours": ["WTA"]},
    {"name": "Wimbledon",               "short": "Wimbledon",   "surface": "grass",
     "start": date(2026, 6, 29), "end": date(2026, 7, 12), "category": "Grand Slam",
     "tours": ["ATP", "WTA"]},
    # ── QUADRA DURA (agosto-setembro 2026) ──
    {"name": "Masters 1000 de Montreal","short": "Montreal",    "surface": "hard",
     "start": date(2026, 8,  3), "end": date(2026, 8,  9), "category": "M1000",
     "tours": ["ATP"]},
    {"name": "WTA 1000 de Montreal",    "short": "Montreal WTA","surface": "hard",
     "start": date(2026, 8,  3), "end": date(2026, 8,  9), "category": "WTA 1000",
     "tours": ["WTA"]},
    {"name": "Masters 1000 de Cincinnati","short": "Cincinnati","surface": "hard",
     "start": date(2026, 8, 10), "end": date(2026, 8, 16), "category": "M1000",
     "tours": ["ATP", "WTA"]},
    {"name": "US Open",                 "short": "US Open",     "surface": "hard",
     "start": date(2026, 8, 24), "end": date(2026, 9,  6), "category": "Grand Slam",
     "tours": ["ATP", "WTA"]},
]

# ── Pipeline automático — o que roda em cada dia da semana ────────────────────
WEEKLY_AUTO_SCHEDULE = {
    "seg": [
        {"time": "08:00", "type": "update",    "desc": "Atualiza rankings Sackmann"},
        {"time": "09:00", "type": "daily",     "desc": "Pipeline diário (trends → carrossel + story + reel)"},
        {"time": "10:00", "type": "stories",   "desc": "Stories autônomos"},
        {"time": "10:30", "type": "draw-path", "desc": "Carrosséis de chaveamento (início de torneio)"},
        {"time": "14:00", "type": "stories",   "desc": "Stories autônomos"},
        {"time": "19:00", "type": "stories",   "desc": "Stories autônomos"},
    ],
    "ter": [
        {"time": "09:00", "type": "daily",   "desc": "Pipeline diário"},
        {"time": "10:00", "type": "stories", "desc": "Stories autônomos"},
        {"time": "14:00", "type": "stories", "desc": "Stories autônomos"},
        {"time": "19:00", "type": "stories", "desc": "Stories autônomos"},
    ],
    "qua": [
        {"time": "09:00", "type": "daily",   "desc": "Pipeline diário"},
        {"time": "10:00", "type": "stories", "desc": "Stories autônomos"},
        {"time": "14:00", "type": "stories", "desc": "Stories autônomos"},
        {"time": "19:00", "type": "stories", "desc": "Stories autônomos"},
    ],
    "qui": [
        {"time": "09:00", "type": "daily",   "desc": "Pipeline diário"},
        {"time": "10:00", "type": "stories", "desc": "Stories autônomos"},
        {"time": "14:00", "type": "stories", "desc": "Stories autônomos"},
        {"time": "19:00", "type": "stories", "desc": "Stories autônomos"},
    ],
    "sex": [
        {"time": "09:00", "type": "daily",   "desc": "Pipeline diário"},
        {"time": "10:00", "type": "stories", "desc": "Stories autônomos"},
        {"time": "14:00", "type": "stories", "desc": "Stories autônomos"},
        {"time": "19:00", "type": "stories", "desc": "Stories autônomos"},
    ],
    "sab": [
        {"time": "09:00", "type": "daily",   "desc": "Pipeline diário"},
        {"time": "10:00", "type": "stories", "desc": "Stories autônomos"},
        {"time": "14:00", "type": "ranking", "desc": "Ranking semanal (quando aplicável)"},
        {"time": "19:00", "type": "stories", "desc": "Stories autônomos"},
    ],
    "dom": [
        {"time": "09:00", "type": "daily",   "desc": "Pipeline diário"},
        {"time": "10:00", "type": "stories", "desc": "Stories autônomos"},
        {"time": "14:00", "type": "stories", "desc": "Stories autônomos"},
        {"time": "19:00", "type": "stories", "desc": "Stories autônomos"},
    ],
}

# ── Posts especiais planejados (adicionar manualmente) ────────────────────────
SPECIAL_POSTS = [
    {"date": date(2026, 5, 11), "time": "09:00", "type": "draw-path",
     "desc": "Chaveamento Roma — ATP e WTA (Fonseca e Bia em destaque)"},
    {"date": date(2026, 5, 24), "time": "09:00", "type": "rg-launch",
     "desc": "Lançamento Roland Garros — pacote completo (carrossel preview + stories)"},
    {"date": date(2026, 5, 24), "time": "10:00", "type": "draw-path",
     "desc": "Chaveamento Roland Garros — ATP e WTA"},
]

SURFACE_EMOJI = {"clay": "🟠", "grass": "🟢", "hard": "🔵"}
TYPE_EMOJI = {
    "daily":     "🤖",
    "stories":   "📱",
    "draw-path": "🏆",
    "ranking":   "📊",
    "rg-launch": "🎾",
    "live":      "⚡",
    "update":    "🔄",
    "special":   "⭐",
}
DIAS_PT = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]
DIAS_FULL = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


def _get_active_tournament(d: date) -> dict | None:
    for t in TOURNAMENTS_2025:
        if t["start"] <= d <= t["end"]:
            return t
    return None


def _get_next_tournament(d: date) -> dict | None:
    future = [t for t in TOURNAMENTS_2025 if t["start"] > d]
    return min(future, key=lambda t: t["start"]) if future else None


def _days_until(d: date) -> int:
    return (d - date.today()).days


def _render_tournament_badge(t: dict) -> str:
    emoji = SURFACE_EMOJI.get(t["surface"], "🎾")
    tours = "/".join(t["tours"])
    return f"{emoji} {t['name']} ({t['category']} · {tours})"


def print_calendar(days: int = 14):
    today = date.today()
    print()
    print("=" * 64)
    print("  CAFÉ COM TÊNIS — CALENDÁRIO EDITORIAL")
    print(f"  Hoje: {today.strftime('%d/%m/%Y (%A)')}")
    print("=" * 64)

    # ── Torneios ativos e próximos ────────────────────────────────
    active = _get_active_tournament(today)
    if active:
        days_left = (active["end"] - today).days
        print(f"\n📍 TORNEIO EM ANDAMENTO:")
        print(f"   {_render_tournament_badge(active)}")
        print(f"   {active['start'].strftime('%d/%m')} – {active['end'].strftime('%d/%m/%Y')} · {days_left} dias restantes")

    next_t = _get_next_tournament(today)
    if next_t:
        diff = _days_until(next_t["start"])
        print(f"\n⏭  PRÓXIMO TORNEIO ({diff} dias):")
        print(f"   {_render_tournament_badge(next_t)}")
        print(f"   Começa em {next_t['start'].strftime('%d/%m/%Y')}")

    # ── Posts publicados recentemente ─────────────────────────────
    try:
        from utils.dedup import get_recent_posts
        recent = get_recent_posts(hours=48)
        if recent:
            print(f"\n✅ PUBLICADOS RECENTEMENTE ({len(recent)}):")
            for p in recent[:5]:
                dt = datetime.fromisoformat(p["published_at"]).strftime("%d/%m %H:%M")
                desc = p["description"][:55] + "…" if len(p.get("description","")) > 55 else p.get("description","")
                print(f"   {dt} · [{p['post_type']}] {desc}")
    except Exception:
        pass

    # ── Fila de publicação ────────────────────────────────────────
    queue_dir = Path("output/queue")
    if queue_dir.exists():
        items = sorted(queue_dir.iterdir(), reverse=True)
        pending = [i for i in items if i.is_dir()][:5]
        if pending:
            print(f"\n📁 FILA (output/queue/) — {len(list(queue_dir.iterdir()))} itens:")
            for item in pending:
                caption_file = item / "legenda.txt"
                caption_preview = ""
                if caption_file.exists():
                    caption_preview = caption_file.read_text(encoding="utf-8")[:55] + "…"
                print(f"   {item.name}")
                if caption_preview:
                    print(f"      └─ {caption_preview}")

    # ── Calendário dia a dia ──────────────────────────────────────
    print(f"\n📅 PRÓXIMOS {days} DIAS:\n")

    for i in range(days):
        d = today + timedelta(days=i)
        dow = d.weekday()  # 0=segunda
        dow_key = DIAS_PT[dow]
        dow_full = DIAS_FULL[dow]
        is_today = (d == today)

        prefix = "▶  HOJE" if is_today else f"   {dow_full[:3]} {d.strftime('%d/%m')}"

        # Verificar torneio ativo neste dia
        tournament = _get_active_tournament(d)
        t_badge = ""
        if tournament:
            emoji = SURFACE_EMOJI.get(tournament["surface"], "🎾")
            t_badge = f" [{emoji} {tournament['short']}]"

        # Posts especiais neste dia
        specials = [p for p in SPECIAL_POSTS if p["date"] == d]

        # Posts automáticos
        auto_posts = WEEKLY_AUTO_SCHEDULE.get(dow_key, [])

        has_content = bool(specials or auto_posts)
        if not has_content:
            continue

        print(f"{prefix}{t_badge}")

        for sp in specials:
            emoji = TYPE_EMOJI.get("special", "⭐")
            print(f"        {emoji} {sp['time'] if 'time' in sp else '09:00'} · {sp['desc']}")

        # Mostrar automático resumido (não repetir stories a cada linha)
        shown_types = set()
        for post in auto_posts:
            pt = post["type"]
            if pt == "stories" and "stories" in shown_types:
                continue
            shown_types.add(pt)
            emoji = TYPE_EMOJI.get(pt, "🤖")
            desc = post["desc"] if pt != "stories" else "Stories autônomos (10h, 14h, 19h)"
            print(f"        {emoji} {post['time']} · {desc}")

        print()

    # ── Próximos eventos especiais ────────────────────────────────
    print("─" * 64)
    print("  EVENTOS IMPORTANTES FUTUROS:\n")
    for t in TOURNAMENTS_2025:
        diff = _days_until(t["start"])
        if diff < 0:
            continue
        if diff == 0:
            status = "EM ANDAMENTO"
        elif diff == 1:
            status = "AMANHÃ"
        else:
            status = f"em {diff} dias"
        emoji = SURFACE_EMOJI.get(t["surface"], "🎾")
        tours = "/".join(t["tours"])
        print(f"  {emoji} {t['name']:35} {status:12} ({t['start'].strftime('%d/%m')}–{t['end'].strftime('%d/%m')})")
    print()


def print_queue_only():
    queue_dir = Path("output/queue")
    if not queue_dir.exists():
        print("output/queue/ vazia.")
        return

    items = sorted(queue_dir.iterdir(), reverse=True)
    dirs = [i for i in items if i.is_dir()]
    files = [i for i in items if i.is_file()]

    print(f"\n📁 FILA DE PUBLICAÇÃO — {len(dirs)} pastas, {len(files)} arquivos soltos\n")
    for item in dirs[:20]:
        caption_file = item / "legenda.txt"
        slides = list(item.glob("slide_*.png")) + list(item.glob("post.*")) + list(item.glob("reel.*")) + list(item.glob("story.*"))
        content_desc = f"{len(slides)} arquivo(s)" if slides else "pasta vazia"
        caption_preview = ""
        if caption_file.exists():
            caption_preview = caption_file.read_text(encoding="utf-8")[:80]
        print(f"  📂 {item.name} ({content_desc})")
        if caption_preview:
            print(f"     {caption_preview[:80]}…")


if __name__ == "__main__":
    args = sys.argv[1:]

    if "--queue" in args:
        print_queue_only()
    elif "--week" in args:
        print_calendar(days=7)
    else:
        print_calendar(days=14)
