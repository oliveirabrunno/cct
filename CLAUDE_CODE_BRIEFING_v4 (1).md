# ☕🎾 CAFÉ COM TÊNIS — BRIEFING CLAUDE CODE v4.0 (FINAL)
# Identidade definida. Pronto para desenvolvimento.

## IDENTIDADE DA MARCA ✅

```
Nome de exibição : Café com Tênis
Handle Instagram : @cafecomteniss
Email            : cafecomtenis@gmail.com
URL              : instagram.com/cafecomteniss
Status           : Perfil criado e ativo
```

Nome com dupla leitura: "Café com Tênis" (conversa descontraída sobre o esporte)
+ o duplo S sinaliza identidade de canal de comunicação e comunidade.

---

## VISÃO DO PROJETO

Canal de tênis no Instagram que cobre ATP + WTA com conteúdo automatizado:
news, estatísticas, curiosidades, humor, polêmicas, trend topics e análises.

Diferencial: sem rosto, ~90% automatizado, publicando mais rápido e com mais
dados do que qualquer canal manual brasileiro. Atleta em trend topic detectado
automaticamente → carrossel publicado em ~8 minutos.

Meta: 200k seguidores em 6 meses, começando em Roland Garros (25/mai/2026).

Referências de conteúdo: @rodrigobulso, @andreguedestennis, @bonfatennis,
@tennisinsights. Modelo de crescimento: @ri.cred (135k) — carrosséis de
retenção de atenção com gancho forte no slide 1.

---

## STACK TECNOLÓGICA (100% PYTHON — SEM n8n)

```
Python 3.11+         Linguagem principal
APScheduler          Agendamento interno de tarefas
GitHub Actions       CRON externo (trigger gratuito)
Anthropic SDK        Claude API — geração de texto + HTML dos slides
Playwright           Scraping de sites JS-heavy
BeautifulSoup4       Scraping de sites estáticos
feedparser           Google News RSS (sem custo, sem API key)
pandas               Processamento CSVs Sackmann ATP/WTA
Pillow (PIL)         Processamento e composição de imagens localmente
requests             HTTP genérico + download de imagens
Puppeteer (Node.js)  HTML/CSS → PNG via subprocess
FFmpeg               Montagem de MP4 para Reels
ElevenLabs API       TTS voz principal
edge-tts             Fallback TTS gratuito Microsoft (pt-BR-AntonioNeural)
gTTS                 Último fallback TTS
SQLite               Cache + log de posts + deduplicação
```

---

## ═══════════════════════════════════════════════════════
## MÓDULO DE IMAGENS — ESTRATÉGIA COMPLETA
## ═══════════════════════════════════════════════════════

Este é o módulo mais crítico para qualidade visual. Implementar com cuidado.

### FONTES DE IMAGEM (em ordem de prioridade)

---

### FONTE 1 — Wikimedia Commons (PRIORIDADE MÁXIMA)
**Arquivo:** `utils/image_sources/wikimedia.py`

```
URL base da API: https://commons.wikimedia.org/w/api.php
Licença: CC BY / CC BY-SA / Public Domain — uso EDITORIAL GRATUITO
Qualidade: Alta (fotos profissionais de imprensa doadas)
Cobertura: Todos os top 50 ATP/WTA têm fotos de qualidade
Custo: ZERO
```

```python
import requests

WIKIMEDIA_API = "https://commons.wikimedia.org/w/api.php"

def search_player_image(player_name: str, max_results: int = 5) -> list[dict]:
    """
    Busca fotos de atleta no Wikimedia Commons.
    Retorna lista com URL, largura, altura e licença de cada imagem.
    
    Exemplo: search_player_image("João Fonseca tennis")
    """
    params = {
        "action": "query",
        "generator": "search",
        "gsrnamespace": 6,          # namespace de arquivos/imagens
        "gsrsearch": f"{player_name} tennis",
        "gsrlimit": max_results,
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": 800,          # pede versão redimensionada
        "format": "json"
    }
    
    response = requests.get(WIKIMEDIA_API, params=params)
    data = response.json()
    
    results = []
    pages = data.get("query", {}).get("pages", {})
    
    for page in pages.values():
        info = page.get("imageinfo", [{}])[0]
        meta = info.get("extmetadata", {})
        
        # Verificar licença — só aceitar Creative Commons ou Public Domain
        license_short = meta.get("LicenseShortName", {}).get("value", "")
        if not any(ok in license_short for ok in ["CC", "Public Domain", "CC BY"]):
            continue
        
        results.append({
            "url": info.get("thumburl") or info.get("url"),
            "width": info.get("thumbwidth"),
            "height": info.get("thumbheight"),
            "license": license_short,
            "author": meta.get("Artist", {}).get("value", "Unknown"),
            "source": "wikimedia"
        })
    
    return results


def get_best_player_photo(player_name: str) -> dict | None:
    """
    Retorna a melhor foto disponível do atleta no Wikimedia.
    Prioriza fotos em formato retrato (portrait) e alta resolução.
    """
    results = search_player_image(player_name, max_results=10)
    
    if not results:
        return None
    
    # Preferir imagens mais altas que largas (portrait/quadra)
    portraits = [r for r in results if r.get("height", 0) >= r.get("width", 0)]
    
    return portraits[0] if portraits else results[0]
```

**Atletas com boa cobertura confirmada no Wikimedia:**
```
ATP: Sinner, Alcaraz, Djokovic, Zverev, Medvedev, Rublev, Tsitsipas,
     Ruud, Fritz, Shelton, Auger-Aliassime, Musetti, Fonseca
WTA: Swiatek, Sabalenka, Gauff, Rybakina, Pegula, Keys, Paolini,
     Haddad Maia, Andreescu, Badosa
```

---

### FONTE 2 — Instagram Oficial dos Jogadores (via scraping público)
**Arquivo:** `utils/image_sources/player_instagram.py`

```
Método: Playwright → acessa perfil público → captura imagens recentes
Licença: USO EDITORIAL com crédito obrigatório "@cafecomteniss"
Cobertura: 100% dos top 30 ATP/WTA têm Instagram ativo
Qualidade: Altíssima — fotos profissionais que eles próprios postam
Custo: Zero (scraping de perfil público)
```

```python
# Mapa de handles oficiais dos principais atletas
PLAYER_INSTAGRAM_HANDLES = {
    # ATP
    "jannik sinner": "janniksin",
    "carlos alcaraz": "carlitosalcarazgarfia",
    "novak djokovic": "djokernole",
    "alexander zverev": "alexzverev",
    "daniil medvedev": "daniilmedvedev",
    "andrey rublev": "andreyrublev",
    "stefanos tsitsipas": "stefanostsitsipas",
    "casper ruud": "casperruud98",
    "taylor fritz": "taylor_fritz16",
    "ben shelton": "benshelton_",
    "félix auger-aliassime": "felixaugeralliassime",
    "joao fonseca": "joaofonseca__",
    "lorenzo musetti": "lorenzomusetti7",
    "bia haddad": "biahaddadmaia",
    
    # WTA
    "iga swiatek": "iga.swiatek",
    "aryna sabalenka": "aryna.sabalenka",
    "coco gauff": "cocogauff",
    "elena rybakina": "elenarybakina",
    "jessica pegula": "jessicapegula",
    "madison keys": "madison_keys",
    "jasmine paolini": "jasminepaolini4",
}

async def get_player_recent_photo(player_name: str) -> dict | None:
    """
    Acessa perfil público do Instagram do atleta e retorna URL
    da foto mais recente adequada para uso editorial.
    
    IMPORTANTE: Sempre adicionar crédito "📸 @{handle}" na legenda.
    """
    handle = PLAYER_INSTAGRAM_HANDLES.get(player_name.lower())
    if not handle:
        return None
    
    # Playwright acessa perfil público sem autenticação
    # Extrai primeira foto do grid que não seja Reel
    # Retorna URL da imagem em alta resolução
    ...
```

---

### FONTE 3 — Google Images via SerpApi (com filtro de licença)
**Arquivo:** `utils/image_sources/google_images.py`

```
API: SerpApi (100 buscas gratuitas/mês)
Filtro: tbs=sur:fc (apenas Creative Commons)
Uso: Fallback quando Wikimedia e Instagram não têm foto adequada
Custo: Grátis nos primeiros 100/mês, depois $75/mês
```

```python
def search_cc_player_photo(player_name: str) -> dict | None:
    """
    Busca foto do atleta com filtro Creative Commons via SerpApi.
    Usar apenas quando Wikimedia não retornar resultado adequado.
    """
    params = {
        "q": f"{player_name} tennis player",
        "tbm": "isch",              # image search
        "tbs": "sur:fc",            # filtro: uso comercial/editorial livre
        "api_key": SERPAPI_KEY,
        "num": 5
    }
    ...
```

---

### FONTE 4 — Cache Local de Imagens (banco próprio)
**Arquivo:** `utils/image_sources/local_cache.py`

```
Estratégia: Na primeira semana, baixar e indexar manualmente as melhores
fotos de cada atleta do top 50 ATP e top 50 WTA do Wikimedia.
Salvar em data/players/{player_slug}/
Usar sempre que disponível — mais rápido e sem dependência de API.
```

```
data/players/
├── joao-fonseca/
│   ├── headshot_01.jpg       # foto principal (portrait)
│   ├── action_01.jpg         # foto em quadra
│   ├── action_02.jpg
│   └── metadata.json         # licença, autor, fonte
├── jannik-sinner/
│   ├── headshot_01.jpg
│   ├── action_01.jpg
│   └── metadata.json
├── iga-swiatek/
│   └── ...
```

```python
# metadata.json de cada atleta
{
  "player": "João Fonseca",
  "slug": "joao-fonseca",
  "instagram_handle": "joaofonseca__",
  "photos": [
    {
      "file": "headshot_01.jpg",
      "type": "headshot",
      "source": "wikimedia",
      "license": "CC BY-SA 4.0",
      "author": "Carine06",
      "url_original": "https://commons.wikimedia.org/...",
      "downloaded_at": "2026-05-05"
    },
    {
      "file": "action_01.jpg",
      "type": "action",
      "source": "wikimedia",
      "license": "CC BY 4.0",
      "author": "Marianne Bevis",
      "url_original": "https://commons.wikimedia.org/...",
      "downloaded_at": "2026-05-05"
    }
  ]
}
```

---

### GERENCIADOR CENTRAL DE IMAGENS
**Arquivo:** `utils/image_manager.py`

```python
"""
Ponto de entrada único para obter imagem de qualquer atleta.
Tenta as fontes em ordem de prioridade e retorna a melhor disponível.
"""

from utils.image_sources.local_cache import LocalImageCache
from utils.image_sources.wikimedia import get_best_player_photo
from utils.image_sources.player_instagram import get_player_recent_photo
from utils.image_sources.google_images import search_cc_player_photo
from utils.logger import get_logger

log = get_logger(__name__)

class ImageManager:
    
    def __init__(self):
        self.cache = LocalImageCache()
    
    async def get_player_image(
        self,
        player_name: str,
        image_type: str = "any",   # "headshot" | "action" | "any"
        download_if_missing: bool = True
    ) -> dict | None:
        """
        Retorna a melhor imagem disponível do atleta.
        
        Ordem de prioridade:
        1. Cache local (mais rápido, zero custo)
        2. Wikimedia Commons (melhor fonte, CC license)
        3. Instagram oficial do atleta (com crédito)
        4. Google Images com filtro CC (fallback)
        5. Placeholder com cores do brand kit (último recurso)
        
        Retorna dict com: path, url, license, credit_text, source
        """
        
        # 1. Cache local
        cached = self.cache.get(player_name, image_type)
        if cached:
            log.info(f"Imagem de {player_name} encontrada no cache local")
            return cached
        
        if not download_if_missing:
            return self._get_placeholder(player_name)
        
        # 2. Wikimedia Commons
        wiki_photo = get_best_player_photo(player_name)
        if wiki_photo:
            local_path = await self.cache.download_and_save(
                player_name, wiki_photo, image_type
            )
            log.info(f"Imagem de {player_name} baixada do Wikimedia")
            return {
                "path": local_path,
                "source": "wikimedia",
                "license": wiki_photo["license"],
                "credit_text": f"📸 Wikimedia Commons"
            }
        
        # 3. Instagram oficial
        ig_photo = await get_player_recent_photo(player_name)
        if ig_photo:
            log.info(f"Imagem de {player_name} obtida do Instagram")
            return {
                "path": ig_photo["path"],
                "source": "instagram",
                "license": "editorial",
                "credit_text": f"📸 @{ig_photo['handle']}"
            }
        
        # 4. Google Images CC
        google_photo = search_cc_player_photo(player_name)
        if google_photo:
            local_path = await self.cache.download_and_save(
                player_name, google_photo, image_type
            )
            return {
                "path": local_path,
                "source": "google_cc",
                "license": google_photo["license"],
                "credit_text": "📸 Foto: Creative Commons"
            }
        
        # 5. Placeholder (nunca falha)
        log.warning(f"Nenhuma imagem real encontrada para {player_name}, usando placeholder")
        return self._get_placeholder(player_name)
    
    def _get_placeholder(self, player_name: str) -> dict:
        """
        Gera placeholder visual com iniciais do atleta no brand kit.
        Usado quando nenhuma foto está disponível.
        Nunca deve quebrar o pipeline.
        """
        initials = "".join(w[0].upper() for w in player_name.split()[:2])
        return {
            "path": None,
            "initials": initials,
            "source": "placeholder",
            "license": "generated",
            "credit_text": ""
        }
```

---

### PROCESSAMENTO DE IMAGENS PARA O VISUAL
**Arquivo:** `utils/image_processor.py`

```python
"""
Processa imagens de atletas para uso nos templates:
- Recorte inteligente (rosto em destaque)
- Aplicação de filtros do brand kit
- Composição com sobreposições de dados
- Geração de silhuetas/duotone para H2H
"""

from PIL import Image, ImageFilter, ImageEnhance, ImageDraw
import requests
from io import BytesIO

class ImageProcessor:
    
    # Cores do brand kit
    BRAND_DARK = (10, 10, 10)        # #0A0A0A
    BRAND_ACCENT = (200, 241, 53)    # #C8F135 lima
    BRAND_WHITE = (255, 255, 255)
    
    def prepare_for_card(
        self,
        image_path: str,
        target_size: tuple = (400, 500),   # largura x altura do espaço no slide
        style: str = "clean"               # "clean" | "duotone" | "silhouette"
    ) -> Image.Image:
        """
        Prepara imagem de atleta para inserção em card/carrossel.
        
        Estilos disponíveis:
        - clean: foto real com leve vignette nas bordas
        - duotone: efeito dois tons (escuro + lima do brand kit) — ideal para H2H
        - silhouette: silhueta preenchida — para stats onde foto não está disponível
        """
        img = Image.open(image_path).convert("RGB")
        
        # Recortar para foco no rosto/corpo superior
        img = self._smart_crop(img, target_size)
        
        if style == "duotone":
            img = self._apply_duotone(img)
        elif style == "silhouette":
            img = self._apply_silhouette(img)
        else:
            img = self._apply_clean(img)
        
        return img
    
    def _smart_crop(self, img: Image.Image, target: tuple) -> Image.Image:
        """
        Recorta a imagem priorizando a parte superior (onde fica o rosto).
        Não usa detecção facial para manter as dependências simples.
        """
        w, h = img.size
        target_w, target_h = target
        target_ratio = target_w / target_h
        current_ratio = w / h
        
        if current_ratio > target_ratio:
            # Imagem mais larga: cortar nas laterais
            new_w = int(h * target_ratio)
            left = (w - new_w) // 2
            img = img.crop((left, 0, left + new_w, h))
        else:
            # Imagem mais alta: cortar na parte inferior (manter topo = rosto)
            new_h = int(w / target_ratio)
            # Iniciar do topo para preservar o rosto
            top_bias = int(new_h * 0.15)   # 15% de bias para cima
            img = img.crop((0, top_bias, w, top_bias + new_h))
        
        return img.resize(target, Image.LANCZOS)
    
    def _apply_duotone(self, img: Image.Image) -> Image.Image:
        """
        Efeito duotone: converte para escala de cinza e mapeia
        escuras para o tom escuro do brand kit, claras para o lima.
        Ideal para slides de H2H com dois atletas lado a lado.
        """
        gray = img.convert("L")
        duotone = Image.new("RGB", img.size)
        
        dark = self.BRAND_DARK
        light = self.BRAND_ACCENT
        
        pixels = gray.load()
        result = duotone.load()
        
        for y in range(img.height):
            for x in range(img.width):
                t = pixels[x, y] / 255.0
                r = int(dark[0] + (light[0] - dark[0]) * t)
                g = int(dark[1] + (light[1] - dark[1]) * t)
                b = int(dark[2] + (light[2] - dark[2]) * t)
                result[x, y] = (r, g, b)
        
        return duotone
    
    def _apply_clean(self, img: Image.Image) -> Image.Image:
        """
        Foto limpa com leve aumento de contraste e nitidez.
        """
        img = ImageEnhance.Contrast(img).enhance(1.1)
        img = ImageEnhance.Sharpness(img).enhance(1.2)
        return img
    
    def create_h2h_composition(
        self,
        img_a: Image.Image,
        img_b: Image.Image,
        width: int = 1080,
        height: int = 1080
    ) -> Image.Image:
        """
        Composição H2H: dois atletas espelhados com divisor central.
        Atleta A na esquerda (normal), Atleta B na direita (espelhado).
        
        Usado no slide 1 dos carrosséis de H2H pré-jogo.
        """
        canvas = Image.new("RGB", (width, height), self.BRAND_DARK)
        
        half_w = width // 2
        
        # Redimensionar cada atleta para metade do canvas
        img_a_resized = img_a.resize((half_w, height), Image.LANCZOS)
        img_b_resized = img_b.resize((half_w, height), Image.LANCZOS)
        img_b_flipped = img_b_resized.transpose(Image.FLIP_LEFT_RIGHT)
        
        # Colar os dois lados
        canvas.paste(img_a_resized, (0, 0))
        canvas.paste(img_b_flipped, (half_w, 0))
        
        # Linha divisória central em lima
        draw = ImageDraw.Draw(canvas)
        draw.line([(half_w - 2, 0), (half_w + 2, height)], 
                  fill=self.BRAND_ACCENT, width=4)
        
        return canvas
    
    def apply_gradient_overlay(
        self,
        img: Image.Image,
        direction: str = "bottom"   # "bottom" | "top" | "left" | "right"
    ) -> Image.Image:
        """
        Aplica gradiente escuro sobre a imagem para legibilidade do texto.
        Essencial quando texto vai sobre a foto do atleta.
        """
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        w, h = img.size
        
        if direction == "bottom":
            for y in range(h // 2, h):
                alpha = int(200 * (y - h // 2) / (h // 2))
                draw.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))
        
        result = Image.alpha_composite(img.convert("RGBA"), overlay)
        return result.convert("RGB")
```

---

### COMO AS IMAGENS SÃO USADAS EM CADA TIPO DE POST

```python
# generators/visual.py — integração com ImageManager

async def generate_card_with_player(
    post_type: str,
    data: dict,
    content: dict
) -> str:
    """
    Gera card visual com imagem real do atleta integrada.
    
    1. ImageManager busca/baixa a melhor foto disponível
    2. ImageProcessor prepara a imagem (recorte, estilo)
    3. Claude API gera o HTML do card com <img> apontando para o arquivo local
    4. Puppeteer renderiza o HTML completo como PNG
    """
    
    img_manager = ImageManager()
    img_processor = ImageProcessor()
    
    player_name = data.get("player") or data.get("player_a")
    
    # Obter imagem do atleta
    img_data = await img_manager.get_player_image(player_name)
    
    # Processar para o estilo correto
    if img_data["path"]:
        if post_type == "h2h":
            # H2H: duotone para efeito dramático
            player_b = data.get("player_b")
            img_data_b = await img_manager.get_player_image(player_b)
            
            img_a = img_processor.prepare_for_card(img_data["path"], style="duotone")
            img_b = img_processor.prepare_for_card(img_data_b["path"], style="duotone")
            
            composition = img_processor.create_h2h_composition(img_a, img_b)
            bg_path = "/tmp/h2h_bg.jpg"
            composition.save(bg_path)
            
        elif post_type in ["stat_card", "on_this_day"]:
            # Stats: foto clean como background com gradiente
            img = img_processor.prepare_for_card(img_data["path"], (1080, 1080), "clean")
            img = img_processor.apply_gradient_overlay(img, "bottom")
            bg_path = "/tmp/player_bg.jpg"
            img.save(bg_path)
            
        elif post_type == "news":
            # News: foto retrato no lado direito, texto na esquerda
            img = img_processor.prepare_for_card(img_data["path"], (500, 1080), "clean")
            bg_path = "/tmp/news_player.jpg"
            img.save(bg_path)
    
    # Claude gera HTML com as imagens processadas já referenciadas
    prompt = f"""
    Gere HTML/CSS completo para um card Instagram 1080x1080px de {post_type}.
    
    BRAND KIT:
    - Fundo: #0A0A0A (quase preto)
    - Destaque: #C8F135 (verde lima)
    - Texto: #FFFFFF e #AAAAAA
    - Fontes: 'Bebas Neue' (títulos grandes), 'DM Sans' (corpo)
    - Logo "Café com Tênis" canto superior direito, fonte Bebas Neue, cor #C8F135
    
    IMAGEM DO ATLETA disponível em: {bg_path}
    Crédito da imagem: {img_data.get('credit_text', '')}
    
    DADOS DO POST:
    {json.dumps(data, ensure_ascii=False, indent=2)}
    
    CONTEÚDO GERADO:
    {json.dumps(content, ensure_ascii=False, indent=2)}
    
    TIPO DE POST: {post_type}
    
    REGRAS:
    - Use <img src="file://{bg_path}"> para a foto do atleta
    - Inclua crédito da foto discretamente (font-size: 10px, cor: #555)
    - Hierarquia clara: dado principal em destaque, contexto menor
    - Output: APENAS o HTML completo, sem explicações
    """
    
    html = generate_with_claude(prompt)
    png_path = html_to_png(html, f"/tmp/{post_type}_{int(time.time())}.png")
    
    return png_path
```

---

### SCRIPT DE SETUP INICIAL — BANCO DE IMAGENS
**Arquivo:** `scripts/setup_player_images.py`

```python
"""
Rodar UMA VEZ na semana de setup para criar o banco local de imagens.
Baixa as melhores fotos de cada atleta do top 50 ATP e WTA do Wikimedia.
Leva ~30 minutos para rodar.

Uso: python scripts/setup_player_images.py
"""

TOP_50_ATP = [
    "Jannik Sinner", "Carlos Alcaraz", "Alexander Zverev", "Novak Djokovic",
    "Daniil Medvedev", "Casper Ruud", "Andrey Rublev", "Holger Rune",
    "Stefanos Tsitsipas", "Taylor Fritz", "Ben Shelton", "Ugo Humbert",
    "Félix Auger-Aliassime", "Tommy Paul", "Alex de Minaur", "Grigor Dimitrov",
    "Sebastian Korda", "Karen Khachanov", "Frances Tiafoe", "Lorenzo Musetti",
    "Francisco Cerundolo", "Alejandro Davidovich Fokina", "Tallon Griekspoor",
    "Matteo Arnaldi", "Hubert Hurkacz", "Arthur Fils", "Tomas Machac",
    "Jiri Lehecka", "Nicolas Jarry", "João Fonseca",
    # ... completar até top 50
]

TOP_50_WTA = [
    "Aryna Sabalenka", "Iga Swiatek", "Coco Gauff", "Jessica Pegula",
    "Elena Rybakina", "Jasmine Paolini", "Madison Keys", "Emma Navarro",
    "Mirra Andreeva", "Daria Kasatkina", "Marketa Vondrousova", "Caroline Wozniacki",
    "Maria Sakkari", "Beatriz Haddad Maia", "Victoria Azarenka",
    # ... completar até top 50
]

async def setup_all_players():
    manager = ImageManager()
    all_players = TOP_50_ATP + TOP_50_WTA
    
    for player in all_players:
        print(f"Baixando imagens de {player}...")
        
        # Buscar headshot (portrait)
        await manager.get_player_image(player, "headshot", download_if_missing=True)
        
        # Buscar foto em ação (action shot)  
        await manager.get_player_image(player, "action", download_if_missing=True)
        
        # Rate limiting — não sobrecarregar o Wikimedia
        await asyncio.sleep(2)
        
        print(f"  ✅ {player} OK")
    
    print(f"\n✅ Setup concluído: {len(all_players)} atletas processados")
```

---

## ═══════════════════════════════════════════════════════
## MÓDULO DE TREND DETECTION
## ═══════════════════════════════════════════════════════

**Arquivo:** `analytics/trend_detector.py`

```python
"""
Detecta atletas em alta e dispara geração de carrossel automaticamente.

Score composto por 3 sinais:
  - Volume de notícias: +1 ponto por artigo nas últimas 6h (max 5)
  - Reddit: +3 pontos se post com 500+ upvotes nas últimas 12h
  - Google Trends: +2 pontos se interesse > 70/100 no Brasil

Threshold para disparar: score >= 4
"""

import feedparser
import requests
from datetime import datetime, timedelta
from utils.logger import get_logger

log = get_logger(__name__)

TREND_THRESHOLD = 4    # score mínimo para disparar geração

# Atletas monitorados com variações de nome para busca
MONITORED_PLAYERS = {
    "João Fonseca":      ["joao fonseca", "joão fonseca", "fonseca tennis"],
    "Jannik Sinner":     ["sinner", "jannik sinner"],
    "Carlos Alcaraz":    ["alcaraz", "carlos alcaraz", "carlitos"],
    "Iga Swiatek":       ["swiatek", "iga swiatek"],
    "Aryna Sabalenka":   ["sabalenka", "aryna sabalenka"],
    "Novak Djokovic":    ["djokovic", "novak djokovic"],
    "Beatriz Haddad":    ["bia haddad", "beatriz haddad", "haddad maia"],
    "Coco Gauff":        ["gauff", "coco gauff"],
    # ... top 30 jogadores
}

class TrendDetector:
    
    def __init__(self):
        self.news_feed_urls = [
            "https://news.google.com/rss/search?q=tennis+ATP+WTA&hl=pt-BR&gl=BR&ceid=BR:pt-419",
            "https://news.google.com/rss/search?q=tenis&hl=pt-BR&gl=BR&ceid=BR:pt-419",
        ]
    
    async def check_all_players(self) -> list[dict]:
        """
        Verifica todos os atletas monitorados.
        Retorna lista dos que passaram do threshold, ordenados por score.
        """
        trending = []
        
        # Coletar sinais uma vez para todos os atletas
        recent_news = self._fetch_recent_news()
        reddit_posts = self._fetch_reddit_hot()
        
        for player_name, search_terms in MONITORED_PLAYERS.items():
            score = 0
            signals = {}
            
            # Sinal 1: Volume de notícias
            news_count = self._count_news_mentions(recent_news, search_terms)
            news_score = min(news_count, 5)
            score += news_score
            signals["news_count"] = news_count
            
            # Sinal 2: Reddit
            reddit_hit = self._check_reddit_mentions(reddit_posts, search_terms)
            if reddit_hit:
                score += 3
                signals["reddit_post"] = reddit_hit
            
            # Sinal 3: Google Trends (só se já tem pontuação básica, economiza quota)
            if score >= 2:
                trends_score = await self._check_google_trends(player_name)
                score += trends_score
                signals["trends_score"] = trends_score
            
            if score >= TREND_THRESHOLD:
                trending.append({
                    "player": player_name,
                    "score": score,
                    "signals": signals
                })
                log.info(f"🔥 TREND DETECTADO: {player_name} (score: {score})")
        
        return sorted(trending, key=lambda x: x["score"], reverse=True)
    
    def _fetch_recent_news(self) -> list[dict]:
        """Busca notícias das últimas 6h via Google News RSS"""
        cutoff = datetime.now() - timedelta(hours=6)
        articles = []
        
        for url in self.news_feed_urls:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                published = datetime(*entry.published_parsed[:6])
                if published > cutoff:
                    articles.append({
                        "title": entry.title.lower(),
                        "summary": getattr(entry, "summary", "").lower()
                    })
        
        return articles
    
    def _fetch_reddit_hot(self) -> list[dict]:
        """Busca top posts do r/tennis com 500+ upvotes"""
        url = "https://www.reddit.com/r/tennis/hot.json?limit=25"
        headers = {"User-Agent": "TennisBot/1.0"}
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            posts = response.json()["data"]["children"]
            return [
                {
                    "title": p["data"]["title"].lower(),
                    "score": p["data"]["score"],
                    "age_hours": (datetime.now().timestamp() - p["data"]["created_utc"]) / 3600
                }
                for p in posts
                if p["data"]["score"] >= 500 and 
                   (datetime.now().timestamp() - p["data"]["created_utc"]) / 3600 <= 12
            ]
        except Exception as e:
            log.error(f"Reddit fetch falhou: {e}")
            return []
    
    def _count_news_mentions(self, articles: list, search_terms: list) -> int:
        count = 0
        for article in articles:
            text = article["title"] + " " + article["summary"]
            if any(term in text for term in search_terms):
                count += 1
        return count
    
    def _check_reddit_mentions(self, posts: list, search_terms: list) -> dict | None:
        for post in posts:
            if any(term in post["title"] for term in search_terms):
                return post
        return None
    
    async def _check_google_trends(self, player_name: str) -> int:
        """
        Verifica interesse no Google Trends BR.
        Usa Apify actor (pago por uso) apenas quando score já está alto.
        Retorna 0, 1 ou 2 pontos.
        """
        # Implementar via Apify Google Trends actor
        # Por enquanto retornar 0 para não consumir quota
        return 0
```

---

## ARQUITETURA COMPLETA DE ARQUIVOS

```
tennis-content-machine/
│
├── .github/workflows/
│   ├── orchestrator.yml          # pipeline diário 06:00 BRT
│   ├── live_monitor.yml          # scores ao vivo */30min
│   ├── trend_detector.yml        # trends */2h
│   └── weekly_ranking.yml        # segunda 08:00
│
├── orchestrator.py               # cérebro do sistema
│
├── scrapers/
│   ├── base_scraper.py           # rate limiting + retry
│   ├── flashscore.py             # scores ao vivo (Playwright)
│   ├── google_news.py            # RSS feeds
│   ├── reddit_tennis.py          # r/tennis JSON público
│   ├── atp_tour.py               # atptour.com
│   ├── wta_tour.py               # wtatennis.com
│   ├── tennis_news_br.py         # tenisnews.com.br, tenisbrasil.com.br
│   └── tennis_insights.py        # tennisinsights.app
│
├── analytics/
│   ├── trend_detector.py         # ← NOVO: detecta atletas em alta
│   └── performance_tracker.py    # métricas de engajamento
│
├── utils/
│   ├── image_manager.py          # ← NOVO: gerenciador central de imagens
│   ├── image_processor.py        # ← NOVO: Pillow para processar fotos
│   ├── image_sources/
│   │   ├── wikimedia.py          # ← NOVO: Wikimedia Commons API
│   │   ├── player_instagram.py   # ← NOVO: Instagram público
│   │   ├── local_cache.py        # ← NOVO: cache local de imagens
│   │   └── google_images.py      # ← NOVO: SerpApi CC filter
│   ├── h2h.py                    # H2H do Sackmann CSV
│   ├── stats.py                  # stats curiosas + on this day
│   ├── dedup.py                  # deduplicação por hash
│   └── logger.py
│
├── generators/
│   ├── content.py                # Claude API → textos
│   ├── visual.py                 # Claude API → HTML → Puppeteer → PNG
│   ├── carousel.py               # carrosséis multi-slide (modelo ri.cred)
│   ├── reel.py                   # TTS + slides + FFmpeg → MP4
│   ├── tts.py                    # ElevenLabs → edge-tts → gTTS
│   └── screenshot.js             # Puppeteer script
│
├── publisher/
│   ├── instagram.py              # Manus AI / Later API
│   ├── queue.py                  # fila com horários de pico
│   └── story.py                  # stories + enquetes
│
├── data/
│   ├── sackmann/                 # CSVs históricos ATP + WTA
│   ├── players/                  # ← NOVO: banco de imagens por atleta
│   │   ├── joao-fonseca/
│   │   ├── jannik-sinner/
│   │   └── ...
│   ├── database.sqlite
│   └── efemerides.json
│
├── scripts/
│   └── setup_player_images.py    # ← NOVO: setup inicial das imagens
│
├── config/
│   ├── brand_kit.json
│   ├── schedule.json
│   ├── sources.json
│   └── prompts/
│       ├── base_voice.txt
│       ├── stat_card.txt
│       ├── h2h.txt
│       ├── news.txt
│       ├── carousel.txt          # modelo ri.cred
│       ├── trend_carousel.txt    # ← NOVO: prompt para atleta em trend
│       ├── reel_script.txt
│       └── caption.txt
│
├── requirements.txt
├── package.json
└── README.md
```

---

## REQUIREMENTS.TXT (ATUALIZADO)

```
# Claude API
anthropic>=0.25.0

# Scraping
playwright>=1.44.0
beautifulsoup4>=4.12.0
requests>=2.31.0
feedparser>=6.0.11
lxml>=5.2.0

# Data
pandas>=2.2.0
numpy>=1.26.0

# Imagens ← NOVO
Pillow>=10.3.0

# TTS
edge-tts>=6.1.9
gtts>=2.5.1

# Agendamento e utils
python-dotenv>=1.0.0
loguru>=0.7.2
SQLAlchemy>=2.0.0
aiosqlite>=0.20.0

# Async
aiohttp>=3.9.0
aiofiles>=23.2.0
```

---

## PROMPT ESPECÍFICO PARA CARROSSEL DE TREND TOPIC

**Arquivo:** `config/prompts/trend_carousel.txt`

```
Você vai criar um carrossel de 6 slides sobre um atleta que está em alta
no momento. Use os dados fornecidos — notícias recentes, contexto histórico
e estatísticas reais.

MODELO DE RETENÇÃO (baseado no @ri.cred):
- Slide 1: PARA O SCROLL. Dado mais surpreendente do atleta HOJE.
  Use números grandes. Crie tensão sem revelar tudo.
  Exemplo: "19 anos. Masters 1000. Cabeça de chave. Roma."
  
- Slide 2: A NOTÍCIA em contexto. O que aconteceu, por que importa.

- Slide 3: CAMINHO À FRENTE. O que está por vir (chave, adversários).

- Slide 4: HISTÓRIA. O que mudou em relação a onde estava antes.
  "No mesmo torneio ano passado, ele..."

- Slide 5: STAT IMPACTANTE. Um número sobre a carreira/temporada
  que adiciona profundidade. Use dados reais do Sackmann CSV.

- Slide 6: CTA DIRETO. Pergunta que gera comentário + logo.
  Exemplo: "Fonseca chega à semifinal em Roma?" + @cafecomteniss

REGRAS DE RETENÇÃO:
- Cada slide deve fazer o usuário querer ver o próximo
- Nunca resolva a tensão antes do último slide
- Use números específicos (não "muitos vitórias", mas "17 vitórias")
- Compare com contexto que o leitor conhece ("mais jovem desde Nadal em...")

ATLETA: {player_name}
DADOS DA TENDÊNCIA: {trend_signals}
NOTÍCIAS RECENTES: {news_data}
DADOS DE CARREIRA: {career_stats}
CONTEXTO DO TORNEIO: {tournament_data}

OUTPUT JSON:
{{
  "slides": [
    {{"slide": 1, "headline": "", "subtext": "", "visual_note": "foto_action"}},
    {{"slide": 2, "headline": "", "subtext": "", "visual_note": "foto_clean"}},
    {{"slide": 3, "headline": "", "subtext": "", "visual_note": "sem_foto"}},
    {{"slide": 4, "headline": "", "subtext": "", "visual_note": "foto_clean"}},
    {{"slide": 5, "headline": "", "subtext": "", "visual_note": "sem_foto"}},
    {{"slide": 6, "headline": "", "subtext": "CTA aqui", "visual_note": "logo"}}
  ],
  "caption": "legenda completa do post (máx 150 palavras)",
  "hashtags": ["#tennis", "#ATP", ...]
}}
```

---

## ═══════════════════════════════════════════════════════
## MÓDULO DE STORIES — ESTRATÉGIA COMPLETA
## ═══════════════════════════════════════════════════════

Stories é o mecanismo de teaser: dado impactante em formato rápido
que direciona o seguidor para o post/reel completo no feed.
Referência direta: @rodrigobulso — foto do atleta + infográfico flutuante
+ texto de contexto + CTA implícito.

### ANATOMIA DO STORY PERFEITO (modelo Bulso)

```
┌─────────────────────────────┐  1080 × 1920px
│                             │
│   [FOTO DO ATLETA]          │  ← fundo: foto real, ocupa tela toda
│   alta qualidade, quadra    │    com gradiente escuro no terço inferior
│                             │
│                             │
│   ┌─────────────────────┐   │  ← infográfico flutuante
│   │  MOST ATP POINTS    │   │    card branco/escuro com os dados
│   │  17.010 — Djokovic  │   │    não ocupa mais que 40% da tela
│   │  16.480 — Federer   │   │    deixa atleta respirar atrás
│   │  14.350 — Sinner ✓  │   │
│   └─────────────────────┘   │
│                             │
│  Sinner já é o 4º com mais  │  ← texto bold, fundo semi-transparente
│  pontos da história ATP.    │    máximo 2-3 linhas
│  E pode bater o recorde     │
│  ainda em 2026! 🎾🇮🇹       │
│                             │
└─────────────────────────────┘
```

### TIPOS DE STORY A IMPLEMENTAR

**Tipo 1 — TEASER DE POST (principal)**
```
Função: Anunciar que tem post completo no feed
Quando: Sempre que publicar carrossel ou reel relevante
Estrutura:
  - Fundo: foto do atleta (Wikimedia/cache local)
  - Overlay: dado principal do post em destaque
  - Texto: "Detalhes completos no post 👆 vai lá"
  - Sticker: "Ver post" ou seta para cima
Automação: 95% — gerado automaticamente junto com cada post
```

**Tipo 2 — BREAKING NEWS STORY**
```
Função: Notícia quente antes de virar post completo
Quando: Resultado de jogo, lesão, polêmica detectada
Estrutura:
  - Fundo: foto do atleta envolvido
  - Headline grande: "SINNER VENCE ALCARAZ EM ROMA"
  - Sub: placar + dado mais impactante
  - Sem CTA — a notícia é o conteúdo
Automação: 90% — disparado pelo live_monitor
```

**Tipo 3 — RANKING SEMANAL (toda segunda)**
```
Função: Movimentações do ranking ATP/WTA
Quando: Segunda-feira, novo ranking publicado
Estrutura:
  - Fundo escuro com textura de quadra
  - Top 5 com setas ↑↓ de variação
  - Destaque para maiores subidas/quedas
  - "Ranking completo nos destaques 📌"
Automação: 99% — dados do scraper ATP
```

**Tipo 4 — POLL PRÉ-JOGO**
```
Função: Engajamento antes de duelo grande
Quando: 2-3h antes de jogo importante
Estrutura:
  - Composição H2H: foto dos dois atletas
  - Sticker de enquete do Instagram nativo
  - "Quem vence hoje?" [Sinner] [Alcaraz]
Automação: 80% — geração automática, publicação via API
Nota: Sticker de poll nativo do Instagram via API do Later/Manus
```

**Tipo 5 — CURIOSIDADE RÁPIDA (evergreen)**
```
Função: Conteúdo de baixo custo para manter frequência
Quando: Dias sem torneio ou para complementar volume
Estrutura:
  - Fundo: foto temática (quadra, troféu, atleta)
  - Uma stat em destaque: "Você sabia que..."
  - Sem redirecionamento — conteúdo completo no próprio story
Automação: 95%
```

### GERADOR DE STORIES
**Arquivo:** `generators/story.py`

```python
"""
Gera stories automaticamente usando Pillow + templates HTML.

Resolução: 1080 × 1920px (9:16 vertical)
Zona segura: evitar 250px no topo e 400px na base (UI do Instagram)
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import textwrap
from utils.image_manager import ImageManager
from utils.image_processor import ImageProcessor
from generators.content import ContentGenerator
from utils.logger import get_logger

log = get_logger(__name__)

class StoryGenerator:
    
    STORY_W = 1080
    STORY_H = 1920
    SAFE_TOP = 250       # evitar sobreposição com UI do Instagram
    SAFE_BOTTOM = 400    # evitar sobreposição com barra de resposta
    
    BRAND_DARK = (10, 10, 10)
    BRAND_ACCENT = (200, 241, 53)    # lima #C8F135
    BRAND_WHITE = (255, 255, 255)
    BRAND_GRAY = (170, 170, 170)
    
    def __init__(self):
        self.img_manager = ImageManager()
        self.img_processor = ImageProcessor()
        self.content_gen = ContentGenerator()
    
    async def generate_teaser_story(
        self,
        post_data: dict,
        post_type: str,
        player_name: str
    ) -> str:
        """
        Gera story de teaser para um post do feed.
        
        post_data: dados do post original
        post_type: tipo do post (h2h, stat, news, etc.)
        player_name: atleta principal
        
        Retorna: caminho do PNG gerado
        """
        # 1. Obter e preparar foto do atleta
        img_data = await self.img_manager.get_player_image(player_name, "action")
        
        # 2. Criar canvas base
        canvas = Image.new("RGB", (self.STORY_W, self.STORY_H), self.BRAND_DARK)
        
        # 3. Aplicar foto como background (ocupa tela inteira)
        if img_data["path"]:
            player_img = Image.open(img_data["path"]).convert("RGB")
            player_img = self._fit_to_story(player_img)
            canvas.paste(player_img, (0, 0))
        
        # 4. Gradiente escuro no terço inferior para legibilidade
        canvas = self._apply_bottom_gradient(canvas, start_at=0.45)
        
        # 5. Infográfico flutuante (gerado via Claude → HTML → Puppeteer → PNG)
        infographic = await self._generate_floating_infographic(post_data, post_type)
        if infographic:
            # Posicionar no centro-inferior da zona segura
            info_y = int(self.STORY_H * 0.45)
            canvas = self._overlay_png_with_shadow(canvas, infographic, info_y)
        
        # 6. Texto de contexto na parte inferior
        main_text = post_data.get("story_hook") or post_data.get("headline", "")
        canvas = self._draw_bottom_text(canvas, main_text)
        
        # 7. Crédito discreto da imagem
        if img_data.get("credit_text"):
            canvas = self._draw_image_credit(canvas, img_data["credit_text"])
        
        # 8. Logo discreto no topo (zona segura)
        canvas = self._draw_logo(canvas)
        
        # Salvar
        output_path = f"/tmp/story_{post_type}_{int(time.time())}.png"
        canvas.save(output_path, "PNG", quality=95)
        log.info(f"Story gerado: {output_path}")
        
        return output_path
    
    async def generate_breaking_story(self, match_result: dict) -> str:
        """Story de breaking news pós-jogo"""
        player = match_result.get("winner")
        
        canvas = await self._build_base_canvas(player, "action")
        canvas = self._apply_bottom_gradient(canvas, start_at=0.35)
        
        # Placar em destaque
        score_text = match_result.get("score", "")
        winner = match_result.get("winner", "")
        loser = match_result.get("loser", "")
        tournament = match_result.get("tournament", "")
        
        # Headline grande
        headline = f"{winner.upper()} VENCE"
        canvas = self._draw_headline(canvas, headline, y_position=0.50)
        
        # Sub-headline: placar + torneio
        sub = f"{loser} • {score_text} • {tournament}"
        canvas = self._draw_subtext(canvas, sub, y_position=0.62)
        
        # Stat mais impactante do jogo
        stat = match_result.get("top_stat", "")
        if stat:
            canvas = self._draw_stat_pill(canvas, stat, y_position=0.72)
        
        output_path = f"/tmp/story_breaking_{int(time.time())}.png"
        canvas.save(output_path, "PNG", quality=95)
        return output_path
    
    async def generate_h2h_poll_story(
        self,
        player_a: str,
        player_b: str,
        match_context: dict
    ) -> dict:
        """
        Story de H2H com poll.
        Retorna PNG + metadados para a API do Later/Manus adicionar
        o sticker de enquete nativo do Instagram.
        
        A API do Later/Manus suporta adicionar stickers de poll
        programaticamente via endpoint de criação de story.
        """
        # Composição H2H: dois atletas
        img_a_data = await self.img_manager.get_player_image(player_a, "action")
        img_b_data = await self.img_manager.get_player_image(player_b, "action")
        
        canvas = Image.new("RGB", (self.STORY_W, self.STORY_H), self.BRAND_DARK)
        
        if img_a_data["path"] and img_b_data["path"]:
            img_a = Image.open(img_a_data["path"]).convert("RGB")
            img_b = Image.open(img_b_data["path"]).convert("RGB")
            
            # Cada atleta ocupa metade vertical da tela
            half_h = self.STORY_H // 2
            
            img_a_fitted = self._fit_to_story(img_a, (self.STORY_W, half_h))
            img_b_fitted = self._fit_to_story(img_b, (self.STORY_W, half_h))
            img_b_fitted = img_b_fitted.transpose(Image.FLIP_LEFT_RIGHT)
            
            canvas.paste(img_a_fitted, (0, 0))
            canvas.paste(img_b_fitted, (0, half_h))
            
            # Linha divisória horizontal em lima
            draw = ImageDraw.Draw(canvas)
            draw.line([(0, half_h - 2), (self.STORY_W, half_h + 2)],
                     fill=self.BRAND_ACCENT, width=4)
        
        # Nomes dos atletas
        canvas = self._draw_player_name(canvas, player_a.split()[1], 0.40)
        canvas = self._draw_player_name(canvas, player_b.split()[1], 0.90)
        
        # Contexto do jogo
        context_text = f"{match_context.get('tournament')} · {match_context.get('round')}"
        canvas = self._draw_subtext(canvas, context_text, y_position=0.50)
        
        output_path = f"/tmp/story_poll_{int(time.time())}.png"
        canvas.save(output_path, "PNG", quality=95)
        
        # Retornar PNG + configuração do poll para a API
        return {
            "image_path": output_path,
            "poll_config": {
                "question": "Quem vence hoje?",
                "option_a": player_a.split()[1].upper(),
                "option_b": player_b.split()[1].upper(),
                "position_x": 0.5,   # centro horizontal
                "position_y": 0.52   # centro vertical (na linha divisória)
            }
        }
    
    def _fit_to_story(
        self,
        img: Image.Image,
        target: tuple = None
    ) -> Image.Image:
        """Redimensiona imagem para preencher o story sem distorcer"""
        target = target or (self.STORY_W, self.STORY_H)
        tw, th = target
        
        # Calcular escala para cobrir o target completamente
        scale = max(tw / img.width, th / img.height)
        new_w = int(img.width * scale)
        new_h = int(img.height * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        
        # Crop centralizado (bias para cima = preserva rosto)
        left = (new_w - tw) // 2
        top = max(0, int((new_h - th) * 0.25))  # 25% do topo
        return img.crop((left, top, left + tw, top + th))
    
    def _apply_bottom_gradient(
        self,
        canvas: Image.Image,
        start_at: float = 0.4
    ) -> Image.Image:
        """
        Gradiente escuro de start_at (0.0-1.0) até o fundo.
        Essencial para legibilidade do texto sobre a foto.
        """
        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        start_y = int(canvas.height * start_at)
        
        for y in range(start_y, canvas.height):
            progress = (y - start_y) / (canvas.height - start_y)
            alpha = int(220 * progress)   # max opacity 220/255
            draw.line([(0, y), (canvas.width, y)], fill=(0, 0, 0, alpha))
        
        result = Image.alpha_composite(canvas.convert("RGBA"), overlay)
        return result.convert("RGB")
    
    def _draw_bottom_text(
        self,
        canvas: Image.Image,
        text: str,
        y_start: float = 0.72
    ) -> Image.Image:
        """
        Texto principal na parte inferior do story.
        Bold, centralizado, com fundo semi-transparente se necessário.
        """
        draw = ImageDraw.Draw(canvas)
        
        # Fonte bold grande
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 52)
        except:
            font = ImageFont.load_default()
        
        # Quebrar texto em linhas (max 28 chars por linha)
        lines = textwrap.wrap(text, width=28)
        
        y = int(canvas.height * y_start)
        line_height = 62
        
        for line in lines[:3]:  # max 3 linhas
            bbox = draw.textbbox((0, 0), line, font=font)
            text_w = bbox[2] - bbox[0]
            x = (canvas.width - text_w) // 2
            
            # Sombra para legibilidade
            draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 200))
            draw.text((x, y), line, font=font, fill=self.BRAND_WHITE)
            
            y += line_height
        
        return canvas
    
    async def _generate_floating_infographic(
        self,
        post_data: dict,
        post_type: str
    ) -> Image.Image | None:
        """
        Gera o infográfico flutuante que aparece sobre a foto.
        Usa Claude API → HTML → Puppeteer → PNG recortado.
        
        Tamanho: ~600 × 400px (será redimensionado para caber no story)
        Estilo: fundo branco ou escuro com bordas arredondadas
        """
        # Claude gera o HTML do infográfico pequeno
        prompt = f"""
        Gere um infográfico compacto HTML/CSS para inserir como
        elemento flutuante em um story Instagram (600x380px).
        
        Estilo: fundo #FFFFFF, bordas arredondadas 16px,
        sombra sutil, dados em destaque, sem logo.
        
        Tipo: {post_type}
        Dados: {json.dumps(post_data, ensure_ascii=False)}
        
        Retorne APENAS o HTML completo.
        """
        
        html = self.content_gen.generate_with_claude_raw(prompt)
        if not html:
            return None
        
        # Puppeteer renderiza o infográfico como PNG
        png_path = html_to_png(html, "/tmp/infographic_float.png", 600, 380)
        
        if not png_path or not os.path.exists(png_path):
            return None
        
        return Image.open(png_path).convert("RGBA")
    
    def _overlay_png_with_shadow(
        self,
        canvas: Image.Image,
        overlay: Image.Image,
        y_center: int,
        max_width: int = 880
    ) -> Image.Image:
        """
        Cola um PNG com transparência sobre o canvas,
        centralizado horizontalmente, com sombra sutil.
        """
        # Redimensionar se necessário
        if overlay.width > max_width:
            ratio = max_width / overlay.width
            new_h = int(overlay.height * ratio)
            overlay = overlay.resize((max_width, new_h), Image.LANCZOS)
        
        x = (canvas.width - overlay.width) // 2
        y = y_center - overlay.height // 2
        
        # Converter canvas para RGBA para suportar transparência
        canvas_rgba = canvas.convert("RGBA")
        canvas_rgba.paste(overlay, (x, y), overlay)
        
        return canvas_rgba.convert("RGB")


# INTEGRAÇÃO COM O PUBLISHER
# publisher/story.py

class StoryPublisher:
    """
    Publica stories com suporte a:
    - Imagem simples
    - Imagem + sticker de poll
    - Sequência de stories (múltiplos)
    - Link (para contas com 10k+)
    """
    
    async def publish_teaser(
        self,
        story_path: str,
        related_post_id: str = None
    ) -> bool:
        """
        Publica story de teaser logo após publicar o post principal.
        Se tiver post_id, adiciona sticker "Ver post" (via API).
        """
        # Publicar via Manus AI / Later API
        pass
    
    async def publish_poll(self, story_data: dict) -> bool:
        """
        Publica story com sticker de poll nativo.
        story_data contém: image_path + poll_config
        """
        # Later API suporta polls via endpoint de story creation
        pass
```

### CADÊNCIA DE STORIES NA SEMANA

```python
# config/schedule.json — seção de stories
{
  "stories": {
    "teaser_after_post": true,        # sempre que publicar post importante
    "breaking_immediate": true,        # resultado de jogo, sem delay
    "poll_hours_before_match": 2,      # 2h antes de jogos grandes
    "ranking_monday": "08:30",         # após publicar ranking no feed
    "curiosity_slots": ["12:00", "20:00"]  # slots de curiosidade rápida
  }
}
```

### SEMANA TIPO — STORIES (complementa o calendário do feed)

```
SEG 08:00  Feed: Ranking da semana
SEG 08:30  Story: Teaser do ranking + maior movimentação em destaque

TER 07:30  Story: Poll pré-jogo (se tiver Masters/GS)
TER jogo   Story: Breaking do resultado (automático)
TER +30min Story: Teaser do carrossel de análise

QUA 12:00  Story: Curiosidade rápida (evergreen)

QUI 07:30  Story: Poll pré-jogo
QUI 20:00  Story: Teaser do carrossel H2H do dia seguinte

SEX        Story: Breaking de resultados (automático se tiver jogos)

SAB        Story: Breaking + teaser de análise pós-jogo

DOM 10:00  Story: Teaser do recap semanal
DOM 20:00  Story: Poll "quem é o melhor da semana?"
```

### PROMPT DE GERAÇÃO DE TEXTO PARA STORY

**Arquivo:** `config/prompts/story_teaser.txt`

```
Gere o texto para um story Instagram que serve como teaser
de um post completo no feed.

REGRAS:
- Máximo 3 linhas, máximo 28 caracteres por linha
- Primeira linha: dado mais impactante (gera curiosidade)
- Segunda linha: contexto mínimo
- Terceira linha (opcional): CTA implícito ou emoji de impacto
- NÃO escreva "ver post" ou "acesse o link" — o sticker faz isso
- Tom direto, sem enrolação
- 2-3 emojis no máximo, no final

EXEMPLOS BONS:
  "Sinner já acumulou mais pontos
  do que Federer no pico.
  E pode bater Djokovic em 2026. 🎾🇮🇹"

  "Fonseca. 19 anos.
  Cabeça de chave em Roma.
  Um ano atrás caiu na 1ª rodada."

DADOS DO POST:
{post_data}

OUTPUT: apenas o texto final, sem explicações.
```

---


## CAMADA DE PUBLICAÇÃO — DECISÃO PENDENTE

A camada de publicação é INDEPENDENTE do resto do pipeline.
Construir e testar toda a geração de conteúdo antes de decidir.

### Opções disponíveis (avaliar na Semana 3):

```
OPÇÃO A — Manus AI Instagram Connector (PREFERENCIAL)
  Status  : Beta ativo — verificar acesso em manus.im
  Como    : Conector nativo Instagram dentro do workspace Manus
  Vantagem: Pipeline end-to-end sem código extra de publicação
  Risco   : Instabilidade regulatória (bloqueio China/Meta em aberto)

OPÇÃO B — Meta Graph API (FALLBACK PRINCIPAL)
  Status  : Estável, oficial, gratuito
  Como    : Conta Business + Facebook Page vinculada ao @cafecomteniss
  Vantagem: Sem custo, sem intermediário, suporte oficial Meta
  Risco   : Nenhum — é a API oficial

OPÇÃO C — Later API (FALLBACK SECUNDÁRIO)
  Status  : Estável, pago
  Custo   : ~$15/mês
  Como    : SDK Python, agendamento visual
```

### Como o publisher.py deve ser implementado:

Criar interface abstrata que funciona com qualquer opção:

```python
# publisher/base.py
class BasePublisher:
    async def publish_carousel(self, images: list[str], caption: str) -> bool: ...
    async def publish_reel(self, video: str, caption: str) -> bool: ...
    async def publish_story(self, image: str) -> bool: ...

# publisher/manus_publisher.py    — implementar quando acesso confirmado
# publisher/graph_publisher.py    — implementar como fallback (Semana 3)
# publisher/later_publisher.py    — implementar se necessário
```

### Na Semana 1-2: substituir publicação por output local

Durante desenvolvimento, o "publisher" simplesmente salva os
arquivos em /output/queue/ com metadados JSON para revisão manual:

```python
# publisher/local_publisher.py — usar nas semanas 1 e 2
async def publish_carousel(self, images, caption):
    # Salva PNGs + legenda.txt em /output/queue/YYYY-MM-DD_HH-MM/
    # Você revisa e posta manualmente enquanto testa o pipeline
    pass
```

Isso permite validar qualidade visual e textual dos posts
antes de automatizar a publicação de fato.

---
## ORDEM DE IMPLEMENTAÇÃO (ATUALIZADA)

```
SEMANA 1 — Base + Imagens:
  [ ] Estrutura de pastas completa
  [ ] utils/image_sources/wikimedia.py
  [ ] utils/image_manager.py (só cache local + wikimedia por enquanto)
  [ ] scripts/setup_player_images.py → rodar e popular data/players/
  [ ] utils/image_processor.py (Pillow básico: crop + clean)
  [ ] scrapers/google_news.py + scrapers/reddit_tennis.py
  [ ] utils/h2h.py com Sackmann CSV
  [ ] generators/content.py (Claude API → texto)
  [ ] Testar: gerar card do João Fonseca com foto real

SEMANA 2 — Visual Completo:
  [ ] generators/visual.py (Claude API → HTML com foto → Puppeteer → PNG)
  [ ] generators/carousel.py (modelo ri.cred, 6 slides com fotos)
  [ ] scrapers/flashscore.py (Playwright)
  [ ] analytics/trend_detector.py
  [ ] GitHub Actions: pipeline diário + trend detector */2h
  [ ] Primeiro post real publicado

SEMANA 3 — Vídeo + Publisher:
  [ ] generators/tts.py (ElevenLabs + edge-tts + gTTS)
  [ ] generators/reel.py (slides com fotos + áudio + FFmpeg)
  [ ] publisher/instagram.py + publisher/queue.py
  [ ] utils/image_sources/player_instagram.py (fallback IG)

SEMANA 4 — Refinamento:
  [ ] scrapers restantes (ATP, WTA, portais BR)
  [ ] Ajustar prompts baseado em engajamento real
  [ ] Cobertura ao vivo Roland Garros (25/mai)
  [ ] Métricas e analytics básicos
```

---

## DECISÕES FINALIZADAS ✅

```
✅ NOME DA MARCA    : Café com Tênis
✅ HANDLE           : @cafecomteniss
✅ EMAIL            : cafecomtenis@gmail.com
✅ PERFIL           : Criado e ativo no Instagram

⏳ VOZ DOS REELS — testar e escolher entre:
   pip install edge-tts
   edge-tts --voice pt-BR-AntonioNeural \
     --text "Sinner já tem mais pontos que Federer no pico." \
     --write-media test_antonio.mp3
   edge-tts --voice pt-BR-FranciscaNeural \
     --text "Sinner já tem mais pontos que Federer no pico." \
     --write-media test_francisca.mp3

⏳ PUBLICAÇÃO — Later API (recomendado, mais estável que Manus AI)

🚨 PRIORIDADE MÁXIMA: Roland Garros em 25/mai — 20 dias.
   Semanas 1-2 devem estar prontas antes do início do torneio.
   Pipeline mínimo: scraper + card + carrossel + publicação.
```

---

*Café com Tênis — @cafecomteniss — v4.0 FINAL*
*Stack: Python puro, sem n8n. Imagens: Wikimedia + Instagram oficial + cache local.*
*Meta: 200k seguidores em 6 meses. Roland Garros 2026 é o lançamento.*
