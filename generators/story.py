"""
Gera stories automaticamente via Pillow.
Resolução: 1080 × 1920px (9:16)
Zona segura: 250px topo, 400px base (UI do Instagram)
"""

import json
import os
import time
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from utils.image_manager import ImageManager
from utils.image_processor import ImageProcessor
from generators.content import ContentGenerator
from generators.visual import html_to_png
from utils.logger import get_logger

log = get_logger(__name__)

OUTPUT_DIR = Path("output/queue")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FONTS_FALLBACK = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",   # macOS
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", # Linux
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONTS_FALLBACK:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


class StoryGenerator:

    STORY_W = 1080
    STORY_H = 1920
    SAFE_TOP = 260
    SAFE_BOTTOM = 420

    BRAND_DARK   = (10, 10, 10)
    BRAND_ACCENT = (200, 241, 53)
    BRAND_WHITE  = (255, 255, 255)
    BRAND_GRAY   = (170, 170, 170)

    def __init__(self):
        self.img_manager   = ImageManager()
        self.img_processor = ImageProcessor()
        self.content_gen   = ContentGenerator()

    # ─── TEASER DE POST ───────────────────────────────────────────────────────

    async def generate_teaser_story(
        self,
        post_data: dict,
        post_type: str,
        player_name: str,
    ) -> str:
        canvas = await self._build_base_canvas(player_name, "action")
        canvas = self._apply_gradient(canvas, start_at=0.40)

        # Infográfico flutuante (card com dado chave)
        infographic = await self._generate_floating_infographic(post_data, post_type)
        if infographic:
            canvas = self._overlay_element(canvas, infographic, y_frac=0.48)

        # Texto principal
        hook = post_data.get("story_hook") or post_data.get("headline", "")
        if hook:
            canvas = self._draw_text_block(canvas, hook, y_frac=0.74, font_size=58)

        canvas = self._draw_logo(canvas)
        canvas = self._draw_handle(canvas)

        output = str(OUTPUT_DIR / f"story_teaser_{int(time.time())}.png")
        canvas.save(output, "PNG", quality=95)
        log.info(f"Story teaser: {output}")
        return output

    # ─── BREAKING NEWS ────────────────────────────────────────────────────────

    async def generate_breaking_story(self, match_result: dict) -> str:
        winner    = match_result.get("winner", "").upper()
        loser     = match_result.get("loser", "")
        
        canvas = await self._build_base_canvas(winner, "action", fallback_player=loser)
        canvas = self._apply_gradient(canvas, start_at=0.30)
        score     = match_result.get("score", "")
        tournament = match_result.get("tournament", "")

        canvas = self._draw_label(canvas, "RESULTADO", y_frac=0.47)
        canvas = self._draw_headline(canvas, f"{winner} VENCE", y_frac=0.52)
        canvas = self._draw_text_block(
            canvas, f"{loser}  ·  {score}  ·  {tournament}",
            y_frac=0.68, font_size=40, color=self.BRAND_GRAY,
        )

        stat = match_result.get("top_stat", "")
        if stat:
            canvas = self._draw_stat_pill(canvas, stat, y_frac=0.78)

        canvas = self._draw_logo(canvas)
        output = str(OUTPUT_DIR / f"story_breaking_{int(time.time())}.png")
        canvas.save(output, "PNG", quality=95)
        log.info(f"Story breaking: {output}")
        return output

    # ─── H2H POLL ─────────────────────────────────────────────────────────────

    async def generate_h2h_poll_story(
        self, player_a: str, player_b: str, match_context: dict
    ) -> dict:
        canvas = Image.new("RGB", (self.STORY_W, self.STORY_H), self.BRAND_DARK)

        img_a_data = await self.img_manager.get_player_image(player_a, "action")
        img_b_data = await self.img_manager.get_player_image(player_b, "action")

        half_h = self.STORY_H // 2

        if img_a_data and img_a_data.get("path"):
            img_a = Image.open(img_a_data["path"]).convert("RGB")
            img_a = self._fit_to_story(img_a, (self.STORY_W, half_h))
            canvas.paste(img_a, (0, 0))

        if img_b_data and img_b_data.get("path"):
            img_b = Image.open(img_b_data["path"]).convert("RGB")
            img_b = self._fit_to_story(img_b, (self.STORY_W, half_h))
            img_b = img_b.transpose(Image.FLIP_LEFT_RIGHT)
            canvas.paste(img_b, (0, half_h))

        # Linha divisória horizontal em lima
        draw = ImageDraw.Draw(canvas)
        draw.line([(0, half_h - 2), (self.STORY_W, half_h + 2)],
                  fill=self.BRAND_ACCENT, width=5)

        canvas = self._apply_gradient(canvas, 0.35)

        # Nomes e VS
        surname_a = player_a.split()[-1].upper()
        surname_b = player_b.split()[-1].upper()
        canvas = self._draw_headline(canvas, surname_a, y_frac=0.38, font_size=90)
        canvas = self._draw_label(canvas, "VS", y_frac=0.498, color=self.BRAND_ACCENT)
        canvas = self._draw_headline(canvas, surname_b, y_frac=0.54, font_size=90)

        ctx = f"{match_context.get('tournament','') } · {match_context.get('round','')}"
        canvas = self._draw_text_block(canvas, ctx, y_frac=0.86, font_size=38, color=self.BRAND_GRAY)

        canvas = self._draw_logo(canvas)
        output = str(OUTPUT_DIR / f"story_poll_{int(time.time())}.png")
        canvas.save(output, "PNG", quality=95)

        return {
            "image_path": output,
            "poll_config": {
                "question": "Quem vence hoje?",
                "option_a": surname_a,
                "option_b": surname_b,
                "position_x": 0.5,
                "position_y": 0.52,
            },
        }

    # ─── CURIOSIDADE RÁPIDA ────────────────────────────────────────────────────

    async def generate_curiosity_story(self, stat: str, context: str, player_name: str = "") -> str:
        canvas = await self._build_base_canvas(player_name, "headshot") if player_name else \
                 Image.new("RGB", (self.STORY_W, self.STORY_H), self.BRAND_DARK)

        canvas = self._apply_gradient(canvas, start_at=0.25)
        canvas = self._draw_label(canvas, "VOCÊ SABIA?", y_frac=0.38)
        canvas = self._draw_headline(canvas, stat, y_frac=0.46, font_size=72)
        canvas = self._draw_text_block(canvas, context, y_frac=0.70, font_size=44)
        canvas = self._draw_logo(canvas)
        canvas = self._draw_handle(canvas)

        output = str(OUTPUT_DIR / f"story_curiosity_{int(time.time())}.png")
        canvas.save(output, "PNG", quality=95)
        log.info(f"Story curiosidade: {output}")
        return output

    # ─── HELPERS ──────────────────────────────────────────────────────────────

    async def _build_base_canvas(self, player_name: str, image_type: str, fallback_player: str = "") -> Image.Image:
        canvas = Image.new("RGB", (self.STORY_W, self.STORY_H), self.BRAND_DARK)
        if not player_name:
            return canvas
            
        img_data = await self.img_manager.get_player_image(player_name, image_type)
        
        if not img_data or not img_data.get("path"):
            if fallback_player:
                log.warning(f"Sem foto para {player_name} — tentando foto do adversário {fallback_player}")
                img_data = await self.img_manager.get_player_image(fallback_player, image_type)
                
        if img_data and img_data.get("path"):
            try:
                player_img = Image.open(img_data["path"]).convert("RGB")
                player_img = self._fit_to_story(player_img)
                canvas.paste(player_img, (0, 0))
            except Exception as e:
                log.error(f"Falha ao processar imagem para story base canvas: {e}")
                
        return canvas

    def _fit_to_story(self, img: Image.Image, target: tuple = None) -> Image.Image:
        target = target or (self.STORY_W, self.STORY_H)
        tw, th = target
        scale = max(tw / img.width, th / img.height)
        new_w, new_h = int(img.width * scale), int(img.height * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - tw) // 2
        top  = max(0, int((new_h - th) * 0.25))
        return img.crop((left, top, left + tw, top + th))

    def _apply_gradient(self, canvas: Image.Image, start_at: float = 0.4) -> Image.Image:
        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        start_y = int(canvas.height * start_at)
        for y in range(start_y, canvas.height):
            progress = (y - start_y) / (canvas.height - start_y)
            alpha = int(225 * progress)
            draw.line([(0, y), (canvas.width, y)], fill=(0, 0, 0, alpha))
        return Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")

    def _draw_headline(
        self, canvas: Image.Image, text: str, y_frac: float, font_size: int = 100,
        color: tuple = None,
    ) -> Image.Image:
        color = color or self.BRAND_WHITE
        draw  = ImageDraw.Draw(canvas)
        font  = _load_font(font_size)
        lines = textwrap.wrap(text, width=16)
        y     = int(canvas.height * y_frac)
        for line in lines[:3]:
            bbox  = draw.textbbox((0, 0), line, font=font)
            tw    = bbox[2] - bbox[0]
            x     = (canvas.width - tw) // 2
            draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0, 180))
            draw.text((x, y), line, font=font, fill=color)
            y += font_size + 8
        return canvas

    def _draw_label(
        self, canvas: Image.Image, text: str, y_frac: float, color: tuple = None
    ) -> Image.Image:
        color = color or self.BRAND_ACCENT
        draw  = ImageDraw.Draw(canvas)
        font  = _load_font(28)
        bbox  = draw.textbbox((0, 0), text, font=font)
        tw    = bbox[2] - bbox[0]
        x     = (canvas.width - tw) // 2
        y     = int(canvas.height * y_frac)
        draw.text((x, y), text, font=font, fill=color)
        return canvas

    def _draw_text_block(
        self, canvas: Image.Image, text: str, y_frac: float,
        font_size: int = 48, color: tuple = None,
    ) -> Image.Image:
        color = color or self.BRAND_WHITE
        draw  = ImageDraw.Draw(canvas)
        font  = _load_font(font_size)
        lines = textwrap.wrap(text, width=26)
        y     = int(canvas.height * y_frac)
        for line in lines[:4]:
            bbox = draw.textbbox((0, 0), line, font=font)
            tw   = bbox[2] - bbox[0]
            x    = (canvas.width - tw) // 2
            draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 160))
            draw.text((x, y), line, font=font, fill=color)
            y += font_size + 6
        return canvas

    def _draw_stat_pill(
        self, canvas: Image.Image, text: str, y_frac: float
    ) -> Image.Image:
        draw   = ImageDraw.Draw(canvas)
        font   = _load_font(36)
        padding = 24
        bbox   = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        pill_w = tw + padding * 2
        pill_h = th + padding
        x      = (canvas.width - pill_w) // 2
        y      = int(canvas.height * y_frac)
        draw.rounded_rectangle(
            [x, y, x + pill_w, y + pill_h],
            radius=pill_h // 2,
            fill=self.BRAND_ACCENT,
        )
        draw.text((x + padding, y + padding // 2), text, font=font, fill=self.BRAND_DARK)
        return canvas

    def _draw_logo(self, canvas: Image.Image) -> Image.Image:
        draw = ImageDraw.Draw(canvas)
        font = _load_font(32)
        text = "CAFÉ COM TÊNIS"
        y    = self.SAFE_TOP - 50
        bbox = draw.textbbox((0, 0), text, font=font)
        tw   = bbox[2] - bbox[0]
        x    = (canvas.width - tw) // 2
        draw.text((x, y), text, font=font, fill=self.BRAND_ACCENT)
        return canvas

    def _draw_handle(self, canvas: Image.Image) -> Image.Image:
        draw = ImageDraw.Draw(canvas)
        font = _load_font(28)
        text = "@cafecomteniss"
        y    = canvas.height - self.SAFE_BOTTOM + 10
        bbox = draw.textbbox((0, 0), text, font=font)
        x    = (canvas.width - (bbox[2] - bbox[0])) // 2
        draw.text((x, y), text, font=font, fill=self.BRAND_GRAY)
        return canvas

    def _overlay_element(
        self, canvas: Image.Image, element: Image.Image, y_frac: float, max_w: int = 880
    ) -> Image.Image:
        if element.width > max_w:
            ratio = max_w / element.width
            element = element.resize((max_w, int(element.height * ratio)), Image.LANCZOS)
        x = (canvas.width - element.width) // 2
        y = int(canvas.height * y_frac) - element.height // 2
        canvas_rgba = canvas.convert("RGBA")
        if element.mode == "RGBA":
            canvas_rgba.paste(element, (x, y), element)
        else:
            canvas_rgba.paste(element, (x, y))
        return canvas_rgba.convert("RGB")

    async def _generate_floating_infographic(self, post_data: dict, post_type: str) -> Image.Image | None:
        prompt = (
            f"Gere um infográfico compacto HTML/CSS 600×380px para inserir como elemento flutuante "
            f"em um story Instagram.\n"
            f"Estilo: fundo #FFFFFF, bordas arredondadas 16px, sombra sutil, dados em destaque, sem logo.\n"
            f"Tipo: {post_type}\nDados: {json.dumps(post_data, ensure_ascii=False)}\n"
            f"Retorne APENAS o HTML completo."
        )
        html = self.content_gen.generate_with_claude_raw(prompt)
        if not html or "<html" not in html.lower():
            return None
        png_path = html_to_png(html, "/tmp/story_infographic.png", 600, 380)
        if not png_path or not Path(png_path).exists():
            return None
        return Image.open(png_path).convert("RGBA")
