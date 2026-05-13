"""
Gerador de cards de estatísticas históricas / recordes.

Uso:
  python orchestrator.py stat-historico "Sinner" "31 vitórias consecutivas em Masters 1000"
  python orchestrator.py stat-historico "Alcaraz" "Mais jovem a vencer 3 Grand Slams diferentes"
  python orchestrator.py stat-historico "Fonseca" "Melhor ranking brasileiro desde Guga"

Fluxo:
  1. Claude recebe jogador + fato e gera o conteúdo completo do card
     (badge, kicker, headline, stats comparativas, caption IG, hashtags)
  2. Busca foto do jogador (prefere troféu / ação impactante)
  3. Renderiza via insight.html com Puppeteer → PNG 1080×1080
  4. Publica no Instagram via Graph API
"""

import asyncio
import base64
import json
import re
import subprocess
import time
from pathlib import Path

from generators.content import ContentGenerator, _load_prompt
from utils.image_manager import ImageManager
from utils.logger import get_logger

log = get_logger(__name__)

OUTPUT_DIR  = Path("output/queue")
TEMPLATE    = Path("config/templates/insight.html")
SCREENSHOT  = Path("generators/screenshot.js")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Mapeamento de superfície pelo mês (para colorir o card)
def _surface_now() -> str:
    from datetime import date
    m = date.today().month
    if m in (5, 6): return "clay"
    if m == 7:      return "grass"
    return "hard"


def _image_to_b64(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    with open(p, "rb") as f:
        return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()


def _html_to_png(html: str, output_path: str) -> str | None:
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as f:
        f.write(html)
        tmp = f.name
    try:
        result = subprocess.run(
            ["node", str(SCREENSHOT), tmp, output_path, "1080", "1080"],
            capture_output=True, text=True, timeout=40,
        )
        if result.returncode != 0:
            log.error(f"Puppeteer erro: {result.stderr[:500]}")
            return None
        return output_path
    except Exception as e:
        log.error(f"Screenshot falhou: {e}")
        return None
    finally:
        try: os.unlink(tmp)
        except: pass


def _build_html(data: dict) -> str:
    template = TEMPLATE.read_text(encoding="utf-8")
    json_str = json.dumps(data, ensure_ascii=False)
    return re.sub(
        r'<script id="post-data" type="application/json">.*?</script>',
        f'<script id="post-data" type="application/json">\n{json_str}\n</script>',
        template,
        flags=re.DOTALL,
    )


async def generate_stat_historico(
    player_name: str,
    stat_fact: str,
    publish: bool = True,
) -> dict | None:
    """
    Gera e (opcionalmente) publica um card de estatística histórica.

    Args:
        player_name: Nome do jogador (ex: "Jannik Sinner")
        stat_fact:   Fato/recorde a destacar (ex: "31 vitórias consecutivas em Masters 1000")
        publish:     Se True, publica no Instagram. Se False, só gera o PNG.

    Returns:
        dict com image_path, caption, hashtags — ou None em caso de falha.
    """
    content_gen = ContentGenerator()
    surface = _surface_now()

    # ── 1. Claude gera todo o conteúdo ─────────────────────────────────────
    log.info(f"Gerando stat histórica: {player_name} | {stat_fact}")

    system = _load_prompt("base_voice") or ""
    prompt = f"""Você é o editor do @cafecomteniss no Instagram (tênis, português brasileiro, tom de bar de esporte).

JOGADOR: {player_name}
FATO/RECORDE: {stat_fact}

Gere o conteúdo completo para um card de estatística histórica no Instagram.

REGRAS DO CARD:
- badge: 1-2 palavras em maiúsculo que categorizam o card. Ex: "HISTÓRIA", "RECORDE", "DADOS", "DOMINÂNCIA"
- kicker: linha de contexto curta. Ex: "RECORDE HISTÓRICO · Masters 1000"
- headline: título impactante do card (máx 8 palavras, MAIÚSCULO, sem introdução)
- vs_line: contexto comparativo. Ex: "Djokovic (30 — recorde anterior)" ou deixe vazio se não houver comparação
- stats: lista de 4-5 estatísticas que contextualizam o feito. Cada stat tem:
    - label: nome da stat (máx 6 palavras)
    - value: valor (número, %, etc.)
    - bar: inteiro 0-100 (proporcional para a barra visual; 100 = máximo)
- caption: legenda Instagram (máx 100 palavras). Tom empolgado, próximo do torcedor.
  Terminar com "Segue @cafecomteniss pra acompanhar cada marco desta temporada 🎾"
- hashtags: lista de 10-12 hashtags relevantes (sem o #, apenas a palavra)

RESPONDA SOMENTE JSON:
{{
  "badge": "",
  "kicker": "",
  "headline": "",
  "vs_line": "",
  "stats": [{{"label":"","value":"","bar":0}}],
  "caption": "",
  "hashtags": []
}}"""

    raw  = content_gen._call_claude(system, prompt, max_tokens=700)
    data = content_gen._parse_json_response(raw)

    if not data:
        log.error("Claude não retornou JSON válido")
        return None

    badge    = data.get("badge", "HISTÓRIA")
    kicker   = data.get("kicker", "RECORDE HISTÓRICO")
    headline = data.get("headline", stat_fact.upper())
    vs_line  = data.get("vs_line", "")
    stats    = data.get("stats", [])
    caption  = data.get("caption", "")
    hashtags = ["#" + h.lstrip("#") for h in data.get("hashtags", [])]

    log.info(f"Badge: {badge} | Headline: {headline}")
    log.info(f"Stats: {len(stats)} itens | Caption: {caption[:80]}...")

    # ── 2. Foto do jogador ──────────────────────────────────────────────────
    img_manager = ImageManager()
    b64 = ""
    for img_type in ("trophy", "action", "any"):
        img_data = await img_manager.get_player_image(
            player_name,
            image_type=img_type,
            search_override=f"{player_name} tennis {img_type}",
        )
        if img_data and img_data.get("path"):
            b64 = _image_to_b64(img_data["path"])
            log.info(f"Foto: {img_data['path']}")
            break

    if not b64:
        log.warning(f"Sem foto para {player_name} — card sem imagem")

    # ── 3. Montar JSON do template ─────────────────────────────────────────
    template_data = {
        "type":        "insight",
        "surface":     surface,
        "badge":       badge,
        "kicker":      kicker,
        "player_name": player_name,
        "vs":          vs_line,
        "score":       "",
        "image":       b64,
        "stats":       stats,
        "headline":    headline,
        "credit":      "Stats: ATP Tour / WTA Tour",
    }

    html = _build_html(template_data)
    ts   = int(time.time())
    slug = player_name.split()[0].lower()
    out  = str(OUTPUT_DIR / f"stat_{slug}_{ts}.png")

    # ── 4. Screenshot ──────────────────────────────────────────────────────
    png = _html_to_png(html, out)
    if not png:
        log.error("Screenshot falhou")
        return None

    log.info(f"Card gerado: {png}")

    result = {
        "image_path": png,
        "caption":    caption,
        "hashtags":   hashtags,
        "headline":   headline,
        "player":     player_name,
    }

    # ── 5. Publicar ────────────────────────────────────────────────────────
    if publish:
        from publisher.graph_publisher import GraphPublisher
        from publisher.rate_limiter import can_publish_feed_post
        from utils.dedup import is_duplicate, register_post

        dedup_key = f"{player_name}_{stat_fact[:40]}".lower().replace(" ", "_")
        if is_duplicate("stat_historico", dedup_key, hours=48):
            log.info(f"Stat histórica já publicada recentemente: {player_name}")
            return result

        if not can_publish_feed_post():
            log.warning("Quota Meta atingida — card salvo localmente, não publicado")
            return result

        pub = GraphPublisher()
        ok  = await pub.publish_post(png, caption, hashtags)
        if ok:
            register_post("stat_historico", dedup_key, description=headline)
            log.info(f"✅ Publicado: {headline}")
        else:
            log.error("Falha ao publicar no Instagram")

    return result
