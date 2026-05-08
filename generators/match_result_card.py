"""
Gera card de resultado de partida estilo ATP Tour / @manualdotenista.
Formato: 1080x1080 — foto do vencedor com overlay dramático, score em destaque, stat contextual.
Publicado em < 5 min após a partida terminar.
"""

import asyncio
import time
from pathlib import Path
from generators.content import ContentGenerator, _load_prompt
from generators.visual import html_to_png, BRAND_KIT
from utils.image_manager import ImageManager
from utils.logger import get_logger

log = get_logger(__name__)

OUTPUT_DIR = Path("output/queue")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CARD_W = 1080
CARD_H = 1080


def _build_result_html(
    headline: str,
    subtext: str,
    stat: str,
    label: str,
    player_img_path: str | None,
    is_upset: bool,
) -> str:
    """Gera HTML do card de resultado. Inspirado no estilo limpo do ATP Tour."""

    bg_image_css = ""
    if player_img_path:
        # Garantir caminho absoluto para o Puppeteer renderizar corretamente
        abs_path = str(Path(player_img_path).resolve())
        bg_image_css = f"background-image: url('file://{abs_path}');"

    accent = "#C8F135" if not is_upset else "#FF6B35"  # lima ou laranja para upset
    label_bg = "#FF6B35" if is_upset else "#C8F135"
    label_color = "#FFFFFF" if is_upset else "#0A0A0A"

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
{BRAND_KIT}

* {{ margin: 0; padding: 0; box-sizing: border-box; }}

body {{
  width: {CARD_W}px;
  height: {CARD_H}px;
  background: #0A0A0A;
  font-family: var(--font-body);
  overflow: hidden;
  position: relative;
}}

/* Foto do vencedor — full bleed */
.bg-photo {{
  position: absolute;
  inset: 0;
  {bg_image_css}
  background-size: cover;
  background-position: center top;
  background-repeat: no-repeat;
}}

/* Gradient escuro de baixo para cima (lê-se de baixo) */
.gradient-overlay {{
  position: absolute;
  inset: 0;
  background: linear-gradient(
    to top,
    rgba(10,10,10,0.98) 0%,
    rgba(10,10,10,0.85) 35%,
    rgba(10,10,10,0.40) 60%,
    rgba(10,10,10,0.10) 100%
  );
}}

/* Label no topo esquerdo */
.label {{
  position: absolute;
  top: 52px;
  left: 52px;
  background: {label_bg};
  color: {label_color};
  font-family: var(--font-body);
  font-weight: 700;
  font-size: 22px;
  letter-spacing: 2px;
  text-transform: uppercase;
  padding: 8px 20px;
  border-radius: 4px;
}}

/* Logo no topo direito */
.logo {{
  position: absolute;
  top: 52px;
  right: 52px;
  color: {accent};
  font-family: var(--font-title);
  font-size: 28px;
  letter-spacing: 1px;
}}

/* Bloco principal de texto (baixo) */
.content {{
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 0 52px 56px;
}}

/* Headline: nome do vencedor + quem perdeu */
.headline {{
  font-family: var(--font-title);
  font-size: 88px;
  line-height: 0.95;
  color: #FFFFFF;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 18px;
  /* sombra para legibilidade sobre foto */
  text-shadow: 2px 3px 12px rgba(0,0,0,0.9);
}}

.headline .winner-accent {{
  color: {accent};
}}

/* Score + torneio */
.subtext {{
  font-family: var(--font-body);
  font-size: 36px;
  font-weight: 700;
  color: rgba(255,255,255,0.80);
  letter-spacing: 1px;
  margin-bottom: 24px;
}}

/* Stat pill — destaque contextual */
.stat-pill {{
  display: inline-flex;
  align-items: center;
  gap: 10px;
  background: rgba(255,255,255,0.10);
  border: 1px solid rgba(255,255,255,0.20);
  border-left: 4px solid {accent};
  padding: 12px 20px;
  border-radius: 6px;
  max-width: 100%;
}}

.stat-pill .stat-icon {{
  font-size: 20px;
}}

.stat-pill .stat-text {{
  font-family: var(--font-body);
  font-size: 28px;
  font-weight: 600;
  color: #FFFFFF;
  line-height: 1.2;
}}

/* Handle */
.handle {{
  position: absolute;
  bottom: 18px;
  right: 52px;
  font-size: 22px;
  color: rgba(255,255,255,0.35);
  font-family: var(--font-body);
}}
</style>
</head>
<body>
  <div class="bg-photo"></div>
  <div class="gradient-overlay"></div>

  <div class="label">{label}</div>
  <div class="logo">CAFÉ COM TÊNIS</div>

  <div class="content">
    <div class="headline">{headline}</div>
    <div class="subtext">{subtext}</div>
    <div class="stat-pill">
      <span class="stat-icon">📊</span>
      <span class="stat-text">{stat}</span>
    </div>
  </div>

  <div class="handle">@cafecomteniss</div>
</body>
</html>"""


async def generate_match_result_card(match_context: dict) -> dict | None:
    """
    Gera card de resultado e retorna dict com image_path, caption, hashtags.
    match_context: retorno de build_match_context() em match_stats.py
    """
    content_gen = ContentGenerator()
    img_manager = ImageManager()

    winner    = match_context["winner"]
    loser     = match_context["loser"]
    tournament = match_context["tournament"]
    round_name = match_context.get("round", "")
    label     = match_context.get("label", "RESULTADO")
    is_upset  = match_context.get("is_upset", False)

    # 1. Gerar conteúdo textual via Claude
    system = _load_prompt("base_voice")
    prompt = _load_prompt("match_result") or ""
    for k, v in match_context.items():
        prompt = prompt.replace(f"{{{k}}}", str(v))

    raw = content_gen._call_claude(system, prompt, max_tokens=1024)
    data = content_gen._parse_json_response(raw)

    if not data:
        log.error(f"Claude não gerou conteúdo para o resultado {winner} vs {loser}")
        return None

    stat          = data.get("stat", f"#{match_context['winner_rank']} vence #{match_context['loser_rank']}")
    caption       = data.get("caption", "")
    headline_card = data.get("headline_card", f"{winner.split()[-1].upper()} VENCE").upper()
    subtext_card  = data.get("subtext_card", f"{match_context['score_formatted']} · {tournament}")
    hashtags      = []

    # Extrair hashtags da caption se presentes
    import re
    hashtags = re.findall(r"#\w+", caption)
    caption_clean = re.sub(r"\s*#\w+", "", caption).strip()

    # 2. Buscar foto do vencedor — passa torneio para Flickr buscar foto específica
    img_data = await img_manager.get_player_image(
        winner,
        image_type="any",
        tournament_name=tournament,
    )
    img_path = img_data.get("path") if img_data else None

    # 3. Gerar HTML
    html = _build_result_html(
        headline=headline_card,
        subtext=subtext_card,
        stat=stat,
        label=label,
        player_img_path=img_path,
        is_upset=is_upset,
    )

    # 4. Renderizar PNG
    output_path = str(OUTPUT_DIR / f"match_result_{int(time.time())}.png")
    result_path = html_to_png(html, output_path, CARD_W, CARD_H)

    if not result_path:
        # Fallback Pillow
        result_path = _pil_fallback_card(match_context, img_path, output_path)

    if not result_path:
        log.error(f"Falha ao gerar card para {winner} vs {loser}")
        return None

    log.info(f"Match result card: {result_path}")
    return {
        "image_path": result_path,
        "caption":    caption_clean or caption,
        "hashtags":   hashtags,
        "match":      match_context,
        "stat":       stat,
    }


def _pil_fallback_card(ctx: dict, bg_path: str | None, output_path: str) -> str | None:
    """Fallback Pillow quando Puppeteer falha."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import textwrap

        W, H = CARD_W, CARD_H
        img = Image.new("RGB", (W, H), (10, 10, 10))

        if bg_path:
            try:
                bg = Image.open(bg_path).convert("RGB")
                scale = max(W / bg.width, H / bg.height)
                bg = bg.resize((int(bg.width * scale), int(bg.height * scale)), Image.LANCZOS)
                x = (bg.width - W) // 2
                y = max(0, int((bg.height - H) * 0.2))
                bg = bg.crop((x, y, x + W, y + H))
                overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                from PIL import ImageDraw as ID
                od = ID.Draw(overlay)
                for row in range(H):
                    alpha = int(150 + (105 * row / H))
                    od.line([(0, row), (W, row)], fill=(0, 0, 0, min(alpha, 255)))
                img = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")
            except Exception:
                pass

        draw = ImageDraw.Draw(img)
        lime  = (200, 241, 53)
        white = (255, 255, 255)
        gray  = (170, 170, 170)

        font_paths = [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        font_path = next((p for p in font_paths if Path(p).exists()), None)

        def font(size):
            if font_path:
                return ImageFont.truetype(font_path, size)
            return ImageFont.load_default()

        # Label
        label = ctx.get("label", "RESULTADO")
        draw.text((52, 52), label, font=font(26), fill=(10, 10, 10))
        bbox = draw.textbbox((52, 52), label, font=font(26))
        draw.rectangle([48, 48, bbox[2]+8, bbox[3]+8], fill=lime)
        draw.text((52, 52), label, font=font(26), fill=(10, 10, 10))

        # Headline
        winner = ctx["winner"].split()[-1].upper()
        loser_name = ctx["loser"].split()[-1].upper()
        headline = f"{winner}\nVENCE\n{loser_name}"
        y = 500
        for line in headline.split("\n"):
            color = lime if line == winner else white
            draw.text((52, y), line, font=font(100), fill=color)
            y += 110

        # Score
        score_text = ctx.get("score_formatted", ctx.get("score", ""))
        draw.text((52, y + 20), f"{score_text}  ·  {ctx['tournament']}", font=font(36), fill=gray)

        # Stat
        stat = ctx.get("stat", "")
        if not stat:
            stat = f"#{ctx['winner_rank']} vence #{ctx['loser_rank']}"
        draw.text((52, H - 120), stat[:60], font=font(28), fill=white)

        img.save(output_path, "PNG", quality=95)
        return output_path
    except Exception as e:
        log.error(f"PIL fallback falhou: {e}")
        return None


async def process_and_publish_match(match: dict, publisher) -> bool:
    """
    Pipeline completo: enriquece → gera card → publica.
    match: dict com winner, loser, score, tournament, round (de check_completed_matches)
    """
    from scrapers.match_stats import build_match_context
    from utils.dedup import is_duplicate, register_post

    winner = match.get("winner", "")
    loser  = match.get("loser", "")
    score  = match.get("score", "")

    # Dedup: não publicar o mesmo jogo duas vezes
    match_key = f"{winner}_{loser}_{score}".lower().replace(" ", "_")
    if is_duplicate("match_result", match_key, hours=12):
        log.info(f"Resultado duplicado, pulando: {winner} vs {loser}")
        return False

    ctx = build_match_context(
        winner=winner,
        loser=loser,
        score=score,
        tournament=match.get("tournament", ""),
        round_name=match.get("round", ""),
    )

    result = await generate_match_result_card(ctx)
    if not result:
        return False

    await publisher.publish_post(result["image_path"], result["caption"], result["hashtags"])
    register_post("match_result", match_key, description=result["caption"][:100])
    log.info(f"Resultado publicado: {winner} def. {loser} {score}")
    return True
