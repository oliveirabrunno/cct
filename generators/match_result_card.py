"""
Gera card de resultado de partida estilo ATP Tour / @manualdotenista.
Formato: 1080x1080 — foto do vencedor com overlay dramático, score em destaque, stat contextual.
Publicado em < 5 min após a partida terminar.
"""

import asyncio
import re
import time
from pathlib import Path
from generators.content import ContentGenerator, _load_prompt
from generators.visual import generate_post
from utils.image_manager import ImageManager
from utils.logger import get_logger

log = get_logger(__name__)

OUTPUT_DIR = Path("output/queue")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ─── Instagram Handles ────────────────────────────────────────────────────────
# DESABILITADO: não há fonte verificada automaticamente para handles de IG.
# Marcar o perfil errado é pior do que não marcar.
# Para habilitar: verifique manualmente cada handle e descomente.
#
# PLAYER_IG_HANDLES: dict[str, str] = {
#     "Jannik Sinner":        "@janniksin",
#     "Carlos Alcaraz":       "@carlitosalcarazof",
#     ...
# }


def _get_player_handle(name: str) -> str | None:
    """
    Retorna o handle verificado do IG para o jogador.
    Retorna None enquanto não houver fonte confiável de verificação.
    """
    # Sem fonte verificada → nunca marcar para evitar mencionar perfil errado
    return None


def _extract_hashtags_and_clean(caption: str) -> tuple[list[str], str]:
    """
    Extrai hashtags reais (#Palavra) da caption e devolve a caption limpa.
    NÃO remove #Número (rankings como #24, #11) do corpo do texto.
    Regra: hashtag real tem pelo menos 1 letra (ex: #CafeComTenis, #Roma).
    Rankings são apenas dígitos (ex: #24) e ficam no texto.
    """
    import re
    # Hashtags reais = # seguido de ao menos 1 letra (pode ter números depois)
    real_hashtag_pattern = re.compile(r'#[a-zA-ZÀ-ÿ][\w]*')
    hashtags = real_hashtag_pattern.findall(caption)
    # Limpar: remover as hashtags reais do corpo (ficam só na lista separada)
    caption_clean = real_hashtag_pattern.sub('', caption).strip()
    # Normalizar espaços múltiplos
    caption_clean = re.sub(r'[ \t]+', ' ', caption_clean)
    caption_clean = re.sub(r'\n{3,}', '\n\n', caption_clean).strip()
    return hashtags, caption_clean



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

    # Extrair hashtags reais SEM remover rankings numéricos (#24, #11)
    hashtags, caption_clean = _extract_hashtags_and_clean(caption)

    # Injetar handle do Instagram do vencedor no início da caption
    winner_handle = _get_player_handle(winner)
    if winner_handle and not caption_clean.startswith(winner_handle):
        # Substituir o nome do vencedor pela menção na primeira ocorrência
        caption_clean = caption_clean.replace(winner, winner_handle, 1)

    # Preparar post_data para o template post.html
    surface_map = {
        "clay": "clay", "saibro": "clay",
        "hard": "hard", "rápida": "hard", "sintética": "hard",
        "grass": "grass", "grama": "grass"
    }
    # Tenta descobrir o piso base no torneio, fallback para neutral
    t_lower = tournament.lower()
    surface = "neutral"
    for pt, en in surface_map.items():
        if pt in t_lower:
            surface = en
            break
    
    # Roma é saibro
    if "roma" in t_lower or "roland garros" in t_lower or "monte-carlo" in t_lower or "madrid" in t_lower:
        surface = "clay"

    post_data = {
        "surface": surface,
        "badge": "ZEBRA!" if is_upset else label,
        "kicker": f"{tournament} · {round_name}",
        "title": headline_card,
        "subtitle": f"{subtext_card}. {stat}",
        "player_image_query": winner
    }

    result_path = await generate_post("match_result", match_context, post_data)

    if not result_path:
        log.error(f"Card abortado para {winner} vs {loser} — sem foto disponível")
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

        W, H = 1080, 1080
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
            except Exception as e:
                log.error(
                    f"_pil_fallback_card: falha ao abrir imagem '{bg_path}': {e} "
                    "— abortando para evitar card sem foto no Instagram"
                )
                return None

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
    from utils.dedup import is_duplicate, register_post, player_posted_recently
    from datetime import datetime, timedelta, timezone

    winner = match.get("winner", "")
    loser  = match.get("loser", "")
    score  = match.get("score", "")
    tournament = match.get("tournament", "")

    # 2ª camada de frescor: rejeitar partidas com timestamp > 48h
    # (1ª camada está no flashscore.py, esta é a salvaguarda final)
    ts_str = match.get("timestamp")
    if ts_str:
        try:
            ts = datetime.fromisoformat(ts_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age = datetime.now(tz=timezone.utc) - ts
            if age > timedelta(hours=48):
                log.warning(
                    f"Partida ignorada (muito antiga — {age.days}d {age.seconds//3600}h): "
                    f"{winner} vs {loser}"
                )
                return False
        except Exception:
            pass  # Sem timestamp válido: deixar passar (flashscore já filtrou)

    # Gate universal: bloqueia se o vencedor apareceu em QUALQUER post recente
    if player_posted_recently(winner, hours=4):
        log.info(f"Resultado bloqueado — {winner} apareceu em post recente (gate universal)")
        return False

    # Dedup: não publicar o mesmo jogo duas vezes
    # Incluir tournament para distinguir rematches em torneios diferentes
    match_key = f"{winner}_{loser}_{score}_{tournament}".lower().replace(" ", "_")
    if is_duplicate("match_result", match_key, hours=12, check_ig=True):
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

    ok = await publisher.publish_post(result["image_path"], result["caption"], result["hashtags"])
    if ok:
        register_post("match_result", match_key, description=result["caption"][:100])
        log.info(f"Resultado publicado: {winner} def. {loser} {score}")
    else:
        log.error(f"Falha ao publicar resultado {winner} def. {loser} — dedup NÃO registrado")
    return ok
