"""
Gerador de conteúdo específico para Roland Garros.
Cria carrosséis, stories e reels para o Grand Slam.

Uso:
    python -c "import asyncio; from generators.roland_garros import run_rg_launch; asyncio.run(run_rg_launch())"
"""

import asyncio
from datetime import date, timedelta
from utils.logger import get_logger
from generators.carousel import generate_trend_carousel
from generators.content import ContentGenerator

log = get_logger(__name__)

RG_START = date(2026, 5, 25)
RG_END   = date(2026, 6, 8)

RG_PLAYERS = [
    "João Fonseca", "Jannik Sinner", "Carlos Alcaraz",
    "Novak Djokovic", "Alexander Zverev", "Daniil Medvedev",
    "Beatriz Haddad", "Iga Swiatek", "Aryna Sabalenka", "Coco Gauff",
]

RG_FACTS = [
    "Rafael Nadal venceu Roland Garros 14 vezes — mais do que qualquer atleta venceu qualquer Grand Slam.",
    "A quadra Philippe-Chatrier tem capacidade para 15.000 espectadores.",
    "O saibro de Roland Garros é feito de tijolo triturado de cor laranja avermelhada.",
    "Steffi Graf é a única tenista a vencer Roland Garros 6 vezes na Era Open.",
    "João Fonseca nasceu em 2006 — o mesmo ano que Nadal venceu seu segundo Roland Garros.",
    "A partida mais longa de Roland Garros durou 6h33 (Mahut × Nieminen, 2004).",
]


async def generate_rg_preview_carousel(days_before: int = 5) -> dict | None:
    """Carrossel de preview com contagem regressiva para Roland Garros."""
    today = date.today()
    days_to_rg = (RG_START - today).days

    content_gen = ContentGenerator()
    tournament_data = {
        "torneio": "Roland Garros 2026",
        "inicio": RG_START.strftime("%d/%m/%Y"),
        "dias_restantes": days_to_rg,
        "superficie": "Saibro (clay)",
        "localizacao": "Paris, França",
        "prize_money": "~€ 53 milhões",
        "top_favoritos_atp": ["Sinner (1)", "Alcaraz (2)", "Zverev (3)", "Fonseca (~30)"],
        "top_favoritos_wta": ["Sabalenka (1)", "Swiatek (2)", "Gauff (3)", "Haddad (~15)"],
        "fato_historico": RG_FACTS[days_before % len(RG_FACTS)],
    }

    signals = {
        "days_to_rg": days_to_rg,
        "type": "preview",
        "news_count": 5,
    }

    news = [
        {"title": f"Roland Garros começa em {days_to_rg} dias", "summary": "Preview do Grand Slam francês"},
        {"title": "Sinner favorito em Paris após domínio na temporada", "summary": ""},
        {"title": "Fonseca busca primeira vitória em Roland Garros principal", "summary": ""},
        {"title": "Bia Haddad quer repetir semifinal histórica", "summary": ""},
    ]

    log.info(f"Gerando carrossel RG preview ({days_to_rg} dias para o torneio)...")
    return await generate_trend_carousel(
        "Roland Garros 2026",
        signals,
        news,
        prompt_override={
            "tournament_data": str(tournament_data),
            "focus": f"Preview {days_to_rg} dias antes do início",
        },
        prompt_template="roland_garros",
    )


async def generate_rg_round_recap(round_name: str, matches: list[dict]) -> dict | None:
    """Carrossel de recap de uma rodada de Roland Garros."""
    signals = {
        "round": round_name,
        "match_count": len(matches),
        "type": "recap",
    }

    news = [
        {"title": f"{m['winner']} vence {m['loser']} {m['score']}", "summary": m.get("highlight", "")}
        for m in matches[:4]
    ]

    player_focus = matches[0]["winner"] if matches else "Roland Garros"
    return await generate_trend_carousel(player_focus, signals, news)


async def run_rg_launch():
    """Gera pacote completo de lançamento para Roland Garros."""
    from publisher.local_publisher import LocalPublisher
    publisher = LocalPublisher()

    log.info("=== Gerando pacote de lançamento Roland Garros ===")

    result = await generate_rg_preview_carousel()
    if result and result.get("image_paths"):
        await publisher.publish_carousel(
            result["image_paths"], result["caption"], result["hashtags"]
        )
        log.info(f"Preview carrossel salvo: {len(result['image_paths'])} slides")
    else:
        log.error("Falha ao gerar carrossel de preview")

    log.info("=== Pacote Roland Garros concluído ===")
