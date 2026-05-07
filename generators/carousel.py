"""
Gera carrosséis completos (modelo @ri.cred de retenção máxima).
Slides → HTML → PNG via Puppeteer, com foto real do atleta.
"""

import asyncio
from generators.content import ContentGenerator
from generators.visual import generate_carousel
from utils.logger import get_logger

log = get_logger(__name__)


async def generate_trend_carousel(
    player_name: str,
    trend_data: dict,
    news: list[dict],
    prompt_override: dict | None = None,
    prompt_template: str = "trend_carousel",
) -> dict:
    content_gen = ContentGenerator()

    data = {
        "player": player_name,
        "player_name": player_name,
        "trend_signals": trend_data,
        "news_data": news[:3],
    }
    if prompt_override:
        data.update(prompt_override)

    slides_content = content_gen.generate_carousel_slides(prompt_template, data)
    if not slides_content or not slides_content.get("slides"):
        log.error(f"Falha ao gerar slides para {player_name}")
        return {}

    slides = slides_content["slides"]
    caption = slides_content.get("caption", "")
    hashtags = slides_content.get("hashtags", [])

    image_paths = await generate_carousel(prompt_template, data, slides)

    return {
        "player": player_name,
        "image_paths": image_paths,
        "caption": caption,
        "hashtags": hashtags,
        "slides_data": slides,
    }


async def generate_h2h_carousel(player_a: str, player_b: str, h2h_data: dict) -> dict:
    content_gen = ContentGenerator()

    data = {
        "player": player_a,
        "player_a": player_a,
        "player_b": player_b,
        "h2h": h2h_data,
    }

    slides_content = content_gen.generate_carousel_slides("h2h", data)
    if not slides_content or not slides_content.get("slides"):
        log.error(f"Falha ao gerar H2H carousel {player_a} vs {player_b}")
        return {}

    slides = slides_content["slides"]
    image_paths = await generate_carousel("h2h", data, slides)

    return {
        "player_a": player_a,
        "player_b": player_b,
        "image_paths": image_paths,
        "caption": slides_content.get("caption", ""),
        "hashtags": slides_content.get("hashtags", []),
    }
