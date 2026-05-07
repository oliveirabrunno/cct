"""
Gera carrosséis de "caminho no torneio" estilo @tennischannel.

Dois formatos:
  - generate_tournament_overview_carousels(): 1 carrossel ATP + 1 WTA,
    cada um com top 4 seeds confirmados + brasileiro em destaque.
    Este é o formato principal (python orchestrator.py draw-path).

  - generate_draw_path_carousel(): carrossel individual por jogador
    (python orchestrator.py draw-path sinner).
"""

import asyncio
from generators.content import ContentGenerator
from generators.visual import generate_carousel
from utils.logger import get_logger

log = get_logger(__name__)


def _make_publisher():
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
                return GraphPublisher()
    except Exception:
        pass
    from publisher.local_publisher import LocalPublisher
    return LocalPublisher()


# ── Carrossel de visão geral do torneio (formato principal) ───────────────────

def _build_seeds_block(top4: list[dict]) -> str:
    lines = []
    for p in top4:
        path_summary = " | ".join(
            f"{s['round']}: {s['opponent']}" for s in p["path"][-3:]
        )
        lines.append(f"  #{p['seed']} {p['name']} ({p.get('country','')}) — {p.get('points',0)} pts")
        lines.append(f"    Caminho: {path_summary}")
    return "\n".join(lines)


def _build_brazilians_block(brazilians: list[dict]) -> str:
    lines = []
    for b in brazilians:
        seed_str = f"Seed #{b['seed']}" if b.get("seed") else f"Ranking #{b.get('rank','?')}"
        path_summary = " | ".join(
            f"{s['round']}: {s['opponent']}" for s in b.get("path", [])[-3:]
        )
        lines.append(f"  {b['name']} — {seed_str}")
        lines.append(f"    Caminho projetado: {path_summary}")
    return "\n".join(lines) if lines else "  (nenhum brasileiro confirmado)"


async def generate_tournament_overview_carousel(tour: str = "atp") -> dict:
    """
    Gera 1 carrossel com top 4 seeds + brasileiro(s) para o tour especificado.
    Slides: capa + 4 seeds + 1 por brasileiro + CTA.
    """
    from scrapers.tournament_draw import get_tournament_overview
    overview = get_tournament_overview(tour)

    if not overview["top4"]:
        log.error(f"Sem seeds para {tour.upper()} — verifique entries_{tour} em tournament_draw.py")
        return {}

    content_gen = ContentGenerator()

    n_bra   = len(overview["brazilians"])
    n_total = 1 + 4 + n_bra + 1  # capa + 4 seeds + brasileiros + CTA

    template_data = {
        "tournament_name": overview["tournament"],
        "tournament_date": overview["date"],
        "surface":         overview["surface"],
        "category":        overview["category"],
        "total_slides":    n_total,
        "n_seeds":         5,   # slides 2-5
        "seeds_text":      _build_seeds_block(overview["top4"]),
        "brazilians_text": _build_brazilians_block(overview["brazilians"]),
        # placeholders para o prompt substituir nomes nos visual_note
        "seed1_name":      overview["top4"][0]["name"] if len(overview["top4"]) > 0 else "",
        "seed2_name":      overview["top4"][1]["name"] if len(overview["top4"]) > 1 else "",
        "seed3_name":      overview["top4"][2]["name"] if len(overview["top4"]) > 2 else "",
        "seed4_name":      overview["top4"][3]["name"] if len(overview["top4"]) > 3 else "",
        "brazilian_name":  overview["brazilians"][0]["name"] if overview["brazilians"] else "",
    }

    slides_content = content_gen.generate_carousel_slides("draw_overview", template_data)
    if not slides_content or not slides_content.get("slides"):
        log.error(f"Falha ao gerar slides de overview {tour.upper()}")
        return {}

    slides   = slides_content["slides"]
    caption  = slides_content.get("caption", "")
    hashtags = slides_content.get("hashtags", [])

    # Enriquecer cada slide com o jogador correto para busca de foto
    seed_map = {s["seed"]: s["name"] for s in overview["top4"]}
    bra_names = [b["name"] for b in overview["brazilians"]]

    for i, slide in enumerate(slides):
        if not slide.get("player"):
            if i == 0 or i == len(slides) - 1:
                slide["player"] = ""
            elif 1 <= i <= 4:
                slide["player"] = seed_map.get(i, "")
            elif i >= 5 and bra_names:
                slide["player"] = bra_names[min(i - 5, len(bra_names) - 1)]

    visual_data = {
        "player":      overview["top4"][0]["name"],
        "player_name": overview["top4"][0]["name"],
        "tournament":  overview["short"],
        "surface":     overview["surface"],
        "tour":        tour.upper(),
    }

    image_paths = await generate_carousel("draw_overview", visual_data, slides)

    label = f"draw_overview_{tour}"
    return {
        "tour":        tour.upper(),
        "tournament":  overview["tournament"],
        "image_paths": image_paths,
        "caption":     caption,
        "hashtags":    hashtags,
        "slides_data": slides,
        "overview":    overview,
        "label":       label,
    }


async def generate_tournament_overview_carousels(publish: bool = True) -> list[dict]:
    """
    Gera e publica 1 carrossel ATP + 1 carrossel WTA do torneio atual.
    """
    from utils.dedup import is_duplicate, register_post
    from scrapers.tournament_draw import CURRENT_TOURNAMENT
    publisher = _make_publisher() if publish else None

    results = []
    for tour in ("atp", "wta"):
        dedup_key = f"draw_overview_{CURRENT_TOURNAMENT['short'].lower()}_{tour}"
        if is_duplicate("draw_overview", dedup_key):
            log.info(f"Draw overview {tour.upper()} já publicado recentemente — pulando")
            continue

        log.info(f"Gerando draw overview {tour.upper()}...")
        result = await generate_tournament_overview_carousel(tour)
        if not result or not result.get("image_paths"):
            log.error(f"Falha no draw overview {tour.upper()}")
            continue

        if publish and publisher:
            await publisher.publish_carousel(
                result["image_paths"], result["caption"], result["hashtags"]
            )
            register_post("draw_overview", dedup_key, description=result["caption"][:100])
            log.info(f"Draw overview {tour.upper()} publicado: {len(result['image_paths'])} slides")

        results.append(result)
        # Aguardar 60s entre publicações para não acionar rate limit do Meta
        if publish and tour == "atp":
            log.info("Aguardando 60s antes de publicar WTA (rate limit Meta)...")
            await asyncio.sleep(60)

    return results


# ── Carrossel individual por jogador (formato antigo, mantido) ────────────────

def _build_path_text(path: list[dict]) -> str:
    return "\n".join(f"  {s['round']}: vs {s['opponent']}" for s in path)


async def generate_draw_path_carousel(player_name: str, tour: str = "atp") -> dict:
    """Carrossel individual mostrando o caminho de um jogador específico."""
    from scrapers.tournament_draw import get_projected_path
    draw_data = get_projected_path(player_name, tour)

    content_gen = ContentGenerator()
    template_data = {
        "player_name":    draw_data["player"],
        "tournament_name": draw_data["tournament"],
        "tournament_date": draw_data["date"],
        "surface":        draw_data["surface"],
        "category":       draw_data["category"],
        "location":       draw_data["location"],
        "player_seed":    draw_data["player_seed"] or "sem seed",
        "player_rank":    draw_data["player_rank"],
        "player_country": draw_data["player_country"],
        "path_text":      _build_path_text(draw_data["path"]),
        "seeds_text":     "\n".join(
            f"  #{s['seed']} {s['name']} ({s.get('country','')}) — {s.get('points',0)} pts"
            for s in draw_data.get("top_seeds", [])[:8]
        ),
        "next_name":      draw_data.get("next_name", ""),
        "next_date":      draw_data.get("next_date", ""),
    }

    slides_content = content_gen.generate_carousel_slides("draw_path", template_data)
    if not slides_content or not slides_content.get("slides"):
        log.error(f"Falha ao gerar draw path para {player_name}")
        return {}

    slides   = slides_content["slides"]
    visual_data = {
        "player":      draw_data["player"],
        "player_name": draw_data["player"],
        "tournament":  draw_data["short"],
        "surface":     draw_data["surface"],
    }
    image_paths = await generate_carousel("draw_path", visual_data, slides)

    return {
        "player":      draw_data["player"],
        "tournament":  draw_data["tournament"],
        "image_paths": image_paths,
        "caption":     slides_content.get("caption", ""),
        "hashtags":    slides_content.get("hashtags", []),
        "slides_data": slides,
    }


if __name__ == "__main__":
    asyncio.run(generate_tournament_overview_carousels(publish=False))
