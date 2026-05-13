import json
import os
import subprocess
import time
import re
import base64
from pathlib import Path
from utils.image_manager import ImageManager
from utils.logger import get_logger

log = get_logger(__name__)

def _image_to_base64(filepath: str) -> str:
    path = Path(filepath)
    if not path.exists():
        return ""
    ext = path.suffix.lower().strip('.')
    mime = "image/png" if ext == "png" else ("image/webp" if ext == "webp" else "image/jpeg")
    with open(path, "rb") as f:
        b64_str = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64_str}"

SCREENSHOT_JS = Path(__file__).parent / "screenshot.js"
TEMPLATE_HTML = Path("config/templates/carousel.html")
POST_TEMPLATE_HTML = Path("config/templates/post.html")
INSIGHT_TEMPLATE_HTML = Path("config/templates/insight.html")
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
    import tempfile
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

async def generate_carousel(
    post_type: str,
    data: dict,
    slides_data: dict,
) -> list[str]:
    """
    Gera as imagens de um carrossel injetando o JSON gerado pelo Claude
    no layout base carousel.html e tirando screenshot de cada div.slide
    """
    if not isinstance(slides_data, dict):
        log.error("slides_data não é um dicionário. Formato inválido.")
        return []

    img_manager = ImageManager()
    img_manager.reset_session()
    
    slides = slides_data.get("slides", [])
    if not slides:
        # Tenta pegar a raiz caso a IA retorne direto a lista (falha de JSON)
        if isinstance(slides_data, list):
            slides = slides_data
            slides_data = {"surface": "neutral", "badge": "Post", "slides": slides}
        else:
            log.error("Nenhum slide encontrado no JSON")
            return []
        
    for slide in slides:
        kind = slide.get("kind", "")
        if kind in ("cover", "image"):
            player_query = slide.get("player_image_query") or data.get("player") or ""
            if player_query:
                img_data = await img_manager.get_player_image(player_query, image_type="any")
                if img_data and img_data.get("path"):
                    slide["image"] = _image_to_base64(img_data['path'])
                else:
                    slide["image"] = ""
            else:
                slide["image"] = ""
                
    # Lê o template
    html_content = TEMPLATE_HTML.read_text(encoding="utf-8")
    
    # Injeta o JSON validando a div
    json_str = json.dumps(slides_data, ensure_ascii=False)
    html_content = re.sub(
        r'<script id="carousel-data" type="application/json">.*?</script>',
        f'<script id="carousel-data" type="application/json">\n{json_str}\n</script>',
        html_content,
        flags=re.DOTALL
    )
    
    # Salva HTML temporário
    ts = int(time.time())
    tmp_html = f"/tmp/carousel_{ts}.html"
    with open(tmp_html, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    output_png_pattern = str(OUTPUT_DIR / f"{post_type}_{ts}_{{index}}.png")
    
    try:
        result = subprocess.run(
            ["node", str(SCREENSHOT_JS), tmp_html, output_png_pattern, "1080", "1350"],
            capture_output=True,
            text=True,
            timeout=45,
        )
        if result.returncode != 0:
            log.error(f"Puppeteer erro: {result.stderr}")
            return []
            
        # Coleta os arquivos gerados (substituindo {index} por 01, 02, etc)
        generated_files = sorted(list(OUTPUT_DIR.glob(f"{post_type}_{ts}_*.png")))
        log.info(f"Geradas {len(generated_files)} imagens para o carrossel")
        return [str(p) for p in generated_files]
    except Exception as e:
        log.error(f"Puppeteer falhou: {e}")
        return []
    finally:
        try:
            os.unlink(tmp_html)
        except:
            pass

async def generate_post(
    post_type: str,
    data: dict,
    post_data: dict,
) -> str | None:
    """
    Gera imagem única usando o template post.html.
    post_data contém o JSON que preencherá o <script id="post-data">.
    """
    if not isinstance(post_data, dict):
        log.error("post_data não é um dicionário.")
        return None

    img_manager = ImageManager()
    
    player_query = post_data.get("player_image_query") or data.get("player") or data.get("winner") or ""
    if player_query:
        img_data = await img_manager.get_player_image(
            player_query, 
            image_type="any", 
            tournament_name=data.get("tournament", "")
        )
        if img_data and img_data.get("path"):
            post_data["image"] = _image_to_base64(img_data['path'])
            post_data["credit"] = img_data.get("credit_text", "")
        else:
            log.warning(f"Sem foto para {player_query}, card pode ficar vazio.")
            post_data["image"] = ""
            
    # Selecionar template: insight.html para scout/h2h com stats, post.html para o resto
    use_insight_template = (
        post_type in ("scout", "insight", "h2h")
        or "stats" in post_data
    ) and INSIGHT_TEMPLATE_HTML.exists()

    template_file = INSIGHT_TEMPLATE_HTML if use_insight_template else POST_TEMPLATE_HTML
    html_content = template_file.read_text(encoding="utf-8")

    if use_insight_template:
        log.debug(f"Usando template insight.html para '{post_type}'")
    
    import re
    json_str = json.dumps(post_data, ensure_ascii=False)
    html_content = re.sub(
        r'<script id="post-data" type="application/json">.*?</script>',
        f'<script id="post-data" type="application/json">\n{json_str}\n</script>',
        html_content,
        flags=re.DOTALL
    )
    
    ts = int(time.time())
    tmp_html = f"/tmp/post_{ts}.html"
    with open(tmp_html, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    output_png = str(OUTPUT_DIR / f"{post_type}_{ts}.png")
    
    try:
        result = subprocess.run(
            ["node", str(SCREENSHOT_JS), tmp_html, output_png, "1080", "1080"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            log.error(f"Puppeteer erro: {result.stderr}")
            return None
        log.info(f"PNG de post gerado: {output_png}")
        return output_png
    except Exception as e:
        log.error(f"Puppeteer falhou: {e}")
        return None
    finally:
        try:
            os.unlink(tmp_html)
        except:
            pass

async def generate_card_with_player(
    post_type: str,
    data: dict,
    content: dict,
    img_manager: ImageManager | None = None,
) -> str | None:
    """Retrocompatibilidade que redireciona para o novo post.html"""
    post_data = {
        "surface": "neutral",
        "badge": "Breaking" if post_type == "match_result" else "Contexto",
        "kicker": "",
        "title": content.get("headline", ""),
        "subtitle": content.get("subtext", ""),
        "player_image_query": data.get("player", "")
    }
    return await generate_post(post_type, data, post_data)
