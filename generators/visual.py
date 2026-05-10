import json
import os
import subprocess
import time
import tempfile
from pathlib import Path
from utils.image_manager import ImageManager
from utils.image_processor import ImageProcessor
from generators.content import ContentGenerator
from utils.logger import get_logger

log = get_logger(__name__)

SCREENSHOT_JS = Path(__file__).parent / "screenshot.js"
OUTPUT_DIR = Path("output/queue")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BRAND_KIT = """
/* Google Fonts */
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@400;700&display=swap');

:root {
  --bg: #0A0A0A;
  --accent: #C8F135;
  --white: #FFFFFF;
  --gray: #AAAAAA;
  --font-title: 'Bebas Neue', sans-serif;
  --font-body: 'DM Sans', sans-serif;
}
"""


def html_to_png(html: str, output_path: str, width: int = 1080, height: int = 1080) -> str | None:
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as f:
        f.write(html)
        tmp_html = f.name

    try:
        result = subprocess.run(
            ["node", str(SCREENSHOT_JS), tmp_html, output_path, str(width), str(height)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            log.error(f"Puppeteer erro: {result.stderr}")
            return None
        log.info(f"PNG gerado: {output_path}")
        return output_path
    except Exception as e:
        log.error(f"html_to_png falhou: {e}")
        return None
    finally:
        os.unlink(tmp_html)


def _pil_fallback_slide(content: dict, bg_path: str | None, output_path: str) -> str | None:
    """Gera slide simples com Pillow quando Claude não está disponível."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import textwrap

        W, H = 1080, 1080
        img = Image.new("RGB", (W, H), (10, 10, 10))

        if bg_path:
            try:
                bg = Image.open(bg_path).convert("RGB").resize((W, H))
                overlay = Image.new("RGBA", (W, H), (0, 0, 0, 180))
                img = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")
            except Exception:
                pass

        draw = ImageDraw.Draw(img)
        lime = (200, 241, 53)
        white = (255, 255, 255)
        gray = (170, 170, 170)

        try:
            font_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 90)
            font_sub   = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
            font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
        except Exception:
            font_title = font_sub = font_small = ImageFont.load_default()

        headline = content.get("headline", "")
        subtext  = content.get("subtext", "")

        draw.rectangle([(0, H - 6), (W, H)], fill=lime)

        y = 320
        for line in textwrap.wrap(headline, width=16):
            draw.text((80, y), line.upper(), font=font_title, fill=white)
            y += 110

        y += 30
        draw.rectangle([(80, y), (120, y + 4)], fill=lime)
        y += 24

        for line in textwrap.wrap(subtext, width=42):
            draw.text((80, y), line, font=font_sub, fill=gray)
            y += 50

        draw.text((80, 60), "café com tênis", font=font_small, fill=lime)
        draw.text((80, H - 50), "@cafecomteniss", font=font_small, fill=(85, 85, 85))

        img.save(output_path, "PNG", optimize=True)
        log.info(f"Fallback PIL slide: {output_path}")
        return output_path
    except Exception as e:
        log.error(f"Fallback PIL falhou: {e}")
        return None


async def generate_card_with_player(
    post_type: str,
    data: dict,
    content: dict,
    img_manager: ImageManager | None = None,
) -> str | None:
    if img_manager is None:
        img_manager = ImageManager()
    img_processor = ImageProcessor()

    # Ler visual_note do slide para decidir imagem e estilo
    visual_note = content.get("visual_note", "foto_clean")
    use_photo = visual_note not in ("sem_foto", "logo")

    # foto_action e foto_clean buscam tipos diferentes para garantir variedade
    image_type_map = {
        "foto_action": "action",
        "foto_clean":  "headshot",
        "foto_headshot": "headshot",
    }
    image_type = image_type_map.get(visual_note, "any")

    player_name = data.get("player") or data.get("player_a") or ""
    img_data = None
    if player_name and use_photo:
        img_data = await img_manager.get_player_image(player_name, image_type=image_type)
        if img_data and img_data.get("source") == "placeholder":
            img_data = None

    # Bloqueia publicação de post sem foto quando a foto é obrigatória
    if use_photo and player_name and img_data is None:
        log.error(
            f"Foto obrigatória para '{player_name}' ({visual_note}) não encontrada — "
            "card abortado para evitar post sem imagem no Instagram"
        )
        return None

    bg_path = None

    if img_data and img_data.get("path"):
        if post_type == "h2h":
            player_b = data.get("player_b", "")
            img_data_b = await img_manager.get_player_image(player_b, image_type="action") if player_b else None

            if img_data_b and img_data_b.get("path"):
                img_a = img_processor.prepare_for_card(img_data["path"], style="duotone")
                img_b = img_processor.prepare_for_card(img_data_b["path"], style="duotone")
                composition = img_processor.create_h2h_composition(img_a, img_b)
                bg_path = f"/tmp/h2h_bg_{int(time.time())}.jpg"
                composition.save(bg_path)

        elif visual_note == "foto_action":
            # Ação: corte landscape, gradiente forte no topo e base
            img = img_processor.prepare_for_card(img_data["path"], (1080, 1080), "clean")
            img = img_processor.apply_gradient_overlay(img, "top")
            img = img_processor.apply_gradient_overlay(img, "bottom")
            bg_path = f"/tmp/action_bg_{int(time.time())}.jpg"
            img.save(bg_path)

        elif visual_note == "foto_clean":
            # Clean: foto limpa com gradiente suave na base
            img = img_processor.prepare_for_card(img_data["path"], (1080, 1080), "clean")
            img = img_processor.apply_gradient_overlay(img, "bottom")
            bg_path = f"/tmp/clean_bg_{int(time.time())}.jpg"
            img.save(bg_path)

        elif post_type in ("stat_card", "on_this_day"):
            img = img_processor.prepare_for_card(img_data["path"], (1080, 1080), "clean")
            img = img_processor.apply_gradient_overlay(img, "bottom")
            bg_path = f"/tmp/player_bg_{int(time.time())}.jpg"
            img.save(bg_path)

        elif post_type == "news":
            img = img_processor.prepare_for_card(img_data["path"], (500, 1080), "clean")
            bg_path = f"/tmp/news_player_{int(time.time())}.jpg"
            img.save(bg_path)

        else:
            img = img_processor.prepare_for_card(img_data["path"], (1080, 1080), "clean")
            img = img_processor.apply_gradient_overlay(img, "bottom")
            bg_path = f"/tmp/card_bg_{int(time.time())}.jpg"
            img.save(bg_path)

    content_gen = ContentGenerator()
    credit_text = (img_data or {}).get("credit_text", "")

    img_tag = (
        f'<img src="file://{bg_path}" style="position:absolute;top:0;left:0;width:100%;height:100%;object-fit:cover;z-index:0;">'
        if bg_path else ""
    )

    # Instruções visuais específicas por visual_note
    visual_instructions = {
        "sem_foto": (
            "SLIDE SEM FOTO: fundo #0A0A0A puro. Crie um layout tipográfico impactante. "
            "Use elementos geométricos (linhas, retângulos) em #C8F135 como decoração. "
            "Destaque o número/stat principal em fonte gigante (200px+) em #C8F135."
        ),
        "logo": (
            "SLIDE FINAL / CTA: fundo #0A0A0A. Logo 'Café com Tênis' em destaque central "
            "em #C8F135, grande. CTA direto abaixo. Fundo com sutil textura ou padrão geométrico leve."
        ),
        "foto_action": (
            "SLIDE COM FOTO DE AÇÃO: foto ocupa toda a tela como background dramático. "
            "Gradiente escuro forte no topo e base. Texto em camada sobre a foto."
        ),
        "foto_clean": (
            "SLIDE COM FOTO LIMPA: foto como background com gradiente suave na base. "
            "Texto principal na parte inferior sobre área escura."
        ),
    }.get(visual_note, "")

    prompt = f"""Gere um card Instagram 1080x1080px completo em HTML/CSS.

BRAND KIT:
{BRAND_KIT}

REGRAS GERAIS:
- Fundo base: #0A0A0A
- Destaque: #C8F135 (verde lima)
- Texto principal: #FFFFFF
- Texto secundário: #AAAAAA
- Títulos: Bebas Neue (importar Google Fonts)
- Corpo: DM Sans
- Logo "Café com Tênis" canto superior direito, Bebas Neue, cor #C8F135, font-size 22px
- Handle @cafecomteniss discreto no rodapé, cor #555
- Numeração do slide (ex: 01/06) canto superior esquerdo, DM Sans, cor #555
- Hierarquia: dado principal GRANDE, contexto menor
- Crédito da foto: font-size 10px, cor #444, canto inferior esquerdo (só se houver foto)
- Output: APENAS o HTML completo (<!DOCTYPE html> ... </html>), sem markdown

INSTRUÇÃO VISUAL DESTE SLIDE:
{visual_instructions}

IMAGEM DO ATLETA (tag HTML):
{img_tag if img_tag else "Sem foto — aplicar instrução 'SLIDE SEM FOTO' acima"}

CRÉDITO DA FOTO: {credit_text}

TIPO DE POST: {post_type}

DADOS:
{json.dumps(data, ensure_ascii=False, indent=2)}

CONTEÚDO GERADO:
{json.dumps(content, ensure_ascii=False, indent=2)}
"""

    html = content_gen.generate_with_claude_raw(prompt)
    if not html or "<html" not in html.lower():
        log.warning("Claude não retornou HTML — usando fallback PIL")
        ts = int(time.time())
        output_path = str(OUTPUT_DIR / f"{post_type}_{ts}.png")
        return _pil_fallback_slide(content, bg_path, output_path)

    ts = int(time.time())
    output_path = str(OUTPUT_DIR / f"{post_type}_{ts}.png")
    return html_to_png(html, output_path)


async def generate_carousel(
    post_type: str,
    data: dict,
    slides: list[dict],
) -> list[str]:
    # Reseta o rastreamento de imagens usadas a cada novo carrossel
    img_manager = ImageManager()
    img_manager.reset_session()

    paths = []
    for i, slide in enumerate(slides, 1):
        slide_player = slide.get("player") or data.get("player") or ""
        slide_data = {**data, "slide_number": i, "total_slides": len(slides), "player": slide_player}
        path = await generate_card_with_player(post_type, slide_data, slide, img_manager=img_manager)
        if path:
            paths.append(path)
    return paths
