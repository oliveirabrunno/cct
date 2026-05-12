"""
Gera o carrossel de lançamento do @cafecomteniss (8 slides).
Output: output/launch_post/ + launch_post_copy.txt
Publicação: Graph API ou local se Meta não disponível.
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from generators.visual import html_to_png, BRAND_KIT
from utils.logger import get_logger

log = get_logger(__name__)

OUTPUT_DIR = Path("output/launch_post")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Fotos dos jogadores (caminhos absolutos para o Puppeteer)
_BASE = Path(__file__).resolve().parent.parent / "data/players"
PHOTO = {
    "fonseca_action1":  str(_BASE / "joao-fonseca/action_01.jpg"),
    "fonseca_action2":  str(_BASE / "joao-fonseca/action_02.jpg"),
    "fonseca_action3":  str(_BASE / "joao-fonseca/action_03.jpg"),
    "fonseca_head":     str(_BASE / "joao-fonseca/headshot_01.jpg"),
    "alcaraz_action":   str(_BASE / "carlos-alcaraz/action_01.jpg"),
    "sinner_action":    str(_BASE / "jannik-sinner/action_01.jpg"),
    "swiatek_action":   str(_BASE / "iga-swiatek/action_01.jpg"),
}


def _bg(key: str, pos: str = "center top") -> str:
    path = PHOTO.get(key, "")
    if not path or not Path(path).exists():
        return ""
    return (
        f"background-image: url('file://{path}');"
        f"background-size: cover;"
        f"background-position: {pos};"
        f"background-repeat: no-repeat;"
    )


# ── Slide 1 — Hook ─────────────────────────────────────────────────────────

def slide_01() -> str:
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
{BRAND_KIT}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  width:1080px; height:1080px;
  background:#0A0A0A;
  font-family:var(--font-body);
  overflow:hidden; position:relative;
}}
.bg {{
  position:absolute; inset:0;
  {_bg("fonseca_action1", "center 20%")}
}}
.grad {{
  position:absolute; inset:0;
  background: linear-gradient(
    160deg,
    rgba(10,10,10,0.92) 0%,
    rgba(10,10,10,0.55) 50%,
    rgba(10,10,10,0.82) 100%
  );
}}
.tag {{
  position:absolute; top:52px; left:52px;
  background:#C8F135; color:#0A0A0A;
  font-family:var(--font-body); font-weight:700;
  font-size:20px; letter-spacing:3px; text-transform:uppercase;
  padding:8px 22px; border-radius:4px;
}}
.logo {{
  position:absolute; top:52px; right:52px;
  color:#C8F135; font-family:var(--font-title);
  font-size:28px; letter-spacing:1px;
}}
.content {{
  position:absolute; bottom:0; left:0; right:0;
  padding:0 56px 64px;
}}
.eyebrow {{
  font-family:var(--font-body); font-weight:700;
  font-size:22px; letter-spacing:4px; text-transform:uppercase;
  color:#C8F135; margin-bottom:20px;
}}
.headline {{
  font-family:var(--font-title);
  font-size:108px; line-height:0.92;
  color:#FFFFFF; text-transform:uppercase;
  letter-spacing:2px; margin-bottom:28px;
  text-shadow:2px 4px 20px rgba(0,0,0,0.9);
}}
.headline span {{ color:#C8F135; }}
.sub {{
  font-family:var(--font-body); font-weight:700;
  font-size:26px; color:rgba(255,255,255,0.65);
  letter-spacing:2px; text-transform:uppercase;
}}
.handle {{
  position:absolute; bottom:20px; right:56px;
  font-size:20px; color:rgba(255,255,255,0.3);
  font-family:var(--font-body);
}}
</style></head><body>
  <div class="bg"></div>
  <div class="grad"></div>
  <div class="tag">novo canal</div>
  <div class="logo">CAFÉ COM TÊNIS</div>
  <div class="content">
    <div class="eyebrow">tênis · dados · português</div>
    <div class="headline">TÊNIS É MAIS<br>DIVERTIDO<br><span>COM DADOS.</span></div>
    <div class="sub">ATP · WTA · Roland Garros · Em Português</div>
  </div>
  <div class="handle">@cafecomteniss</div>
</body></html>"""


# ── Slide 2 — O Problema ────────────────────────────────────────────────────

def slide_02() -> str:
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
{BRAND_KIT}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  width:1080px; height:1080px;
  background:#0A0A0A;
  font-family:var(--font-body);
  overflow:hidden; position:relative;
}}
.logo {{
  position:absolute; top:52px; right:52px;
  color:#C8F135; font-family:var(--font-title);
  font-size:28px; letter-spacing:1px;
}}
.content {{
  position:absolute;
  top:50%; left:56px; right:56px;
  transform:translateY(-50%);
}}
.headline {{
  font-family:var(--font-title);
  font-size:82px; line-height:0.95;
  color:#FFFFFF; text-transform:uppercase;
  letter-spacing:1px; margin-bottom:48px;
}}
.headline span {{ color:#C8F135; }}
.bullets {{
  display:flex; flex-direction:column; gap:22px;
}}
.bullet {{
  display:flex; align-items:flex-start; gap:20px;
}}
.bullet-icon {{
  width:6px; height:6px; min-width:6px;
  background:#C8F135; border-radius:50%;
  margin-top:14px;
}}
.bullet-text {{
  font-family:var(--font-body); font-size:30px;
  color:rgba(255,255,255,0.80); line-height:1.4;
  font-weight:400;
}}
.bullet-text strong {{ color:#FFFFFF; font-weight:700; }}
.divider {{
  width:80px; height:4px; background:#C8F135;
  margin-bottom:40px;
}}
.handle {{
  position:absolute; bottom:20px; right:56px;
  font-size:20px; color:rgba(255,255,255,0.3);
  font-family:var(--font-body);
}}
</style></head><body>
  <div class="logo">CAFÉ COM TÊNIS</div>
  <div class="content">
    <div class="headline">VOCÊ ASSISTE<br><span>ÀS 3H DA<br>MANHÃ.</span></div>
    <div class="divider"></div>
    <div class="bullets">
      <div class="bullet">
        <div class="bullet-icon"></div>
        <div class="bullet-text"><strong>Ninguém analisa depois</strong> — você fica sem contexto</div>
      </div>
      <div class="bullet">
        <div class="bullet-icon"></div>
        <div class="bullet-text">As <strong>stats que mudam tudo</strong> nunca chegam em português</div>
      </div>
      <div class="bullet">
        <div class="bullet-icon"></div>
        <div class="bullet-text"><strong>Fonseca avança</strong> e você não tem onde comemorar</div>
      </div>
      <div class="bullet">
        <div class="bullet-icon"></div>
        <div class="bullet-text"><strong>Bastidores e polêmicas</strong> — sempre perdidos na tradução</div>
      </div>
    </div>
  </div>
  <div class="handle">@cafecomteniss</div>
</body></html>"""


# ── Slide 3 — O que vai encontrar (parte 1) ─────────────────────────────────

def slide_03() -> str:
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
{BRAND_KIT}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  width:1080px; height:1080px;
  background:#0A0A0A;
  font-family:var(--font-body);
  overflow:hidden; position:relative;
}}
.logo {{
  position:absolute; top:52px; right:52px;
  color:#C8F135; font-family:var(--font-title);
  font-size:28px; letter-spacing:1px;
}}
.eyebrow {{
  position:absolute; top:54px; left:56px;
  font-family:var(--font-body); font-weight:700;
  font-size:18px; letter-spacing:4px; text-transform:uppercase;
  color:#C8F135;
}}
.content {{
  position:absolute;
  top:130px; left:56px; right:56px; bottom:60px;
  display:flex; flex-direction:column; justify-content:center;
  gap:0;
}}
.section-title {{
  font-family:var(--font-title);
  font-size:60px; line-height:1;
  color:#FFFFFF; text-transform:uppercase;
  letter-spacing:2px; margin-bottom:44px;
}}
.section-title span {{ color:#C8F135; }}
.cards {{
  display:flex; flex-direction:column; gap:0;
}}
.card {{
  display:flex; align-items:center; gap:28px;
  padding:26px 0;
  border-bottom:1px solid rgba(255,255,255,0.08);
}}
.card:last-child {{ border-bottom:none; }}
.card-num {{
  font-family:var(--font-title); font-size:52px;
  color:#C8F135; line-height:1; min-width:60px;
  text-align:right;
}}
.card-body {{ flex:1; }}
.card-title {{
  font-family:var(--font-body); font-weight:700;
  font-size:30px; color:#FFFFFF;
  margin-bottom:6px;
}}
.card-desc {{
  font-family:var(--font-body); font-size:22px;
  color:rgba(255,255,255,0.55);
}}
.anchor {{
  margin-top:48px;
  font-family:var(--font-body); font-weight:700;
  font-size:24px; color:#C8F135;
  letter-spacing:1px;
}}
.handle {{
  position:absolute; bottom:20px; right:56px;
  font-size:20px; color:rgba(255,255,255,0.3);
  font-family:var(--font-body);
}}
</style></head><body>
  <div class="eyebrow">o que você vai encontrar</div>
  <div class="logo">CAFÉ COM TÊNIS</div>
  <div class="content">
    <div class="section-title">PARTE <span>01</span></div>
    <div class="cards">
      <div class="card">
        <div class="card-num">01</div>
        <div class="card-body">
          <div class="card-title">Breaking results em tempo real</div>
          <div class="card-desc">Antes de qualquer canal em português</div>
        </div>
      </div>
      <div class="card">
        <div class="card-num">02</div>
        <div class="card-body">
          <div class="card-title">H2H e stats que ninguém calcula em PT</div>
          <div class="card-desc">Números que mudam como você vê o jogo</div>
        </div>
      </div>
      <div class="card">
        <div class="card-num">03</div>
        <div class="card-body">
          <div class="card-title">Análises de jogo com dados reais</div>
          <div class="card-desc">Contexto, tendências e o que a stat esconde</div>
        </div>
      </div>
    </div>
    <div class="anchor">⟶ continua no próximo slide</div>
  </div>
  <div class="handle">@cafecomteniss</div>
</body></html>"""


# ── Slide 4 — O que vai encontrar (parte 2) ─────────────────────────────────

def slide_04() -> str:
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
{BRAND_KIT}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  width:1080px; height:1080px;
  background:#0A0A0A;
  font-family:var(--font-body);
  overflow:hidden; position:relative;
}}
.bg {{
  position:absolute; inset:0;
  {_bg("fonseca_head", "center 15%")}
  opacity:0.18;
}}
.logo {{
  position:absolute; top:52px; right:52px;
  color:#C8F135; font-family:var(--font-title);
  font-size:28px; letter-spacing:1px;
}}
.eyebrow {{
  position:absolute; top:54px; left:56px;
  font-family:var(--font-body); font-weight:700;
  font-size:18px; letter-spacing:4px; text-transform:uppercase;
  color:#C8F135;
}}
.content {{
  position:absolute;
  top:130px; left:56px; right:56px; bottom:60px;
  display:flex; flex-direction:column; justify-content:center;
}}
.section-title {{
  font-family:var(--font-title);
  font-size:60px; line-height:1;
  color:#FFFFFF; text-transform:uppercase;
  letter-spacing:2px; margin-bottom:44px;
}}
.section-title span {{ color:#C8F135; }}
.cards {{
  display:flex; flex-direction:column; gap:0;
}}
.card {{
  display:flex; align-items:center; gap:28px;
  padding:24px 0;
  border-bottom:1px solid rgba(255,255,255,0.08);
}}
.card:last-child {{ border-bottom:none; }}
.card-num {{
  font-family:var(--font-title); font-size:52px;
  color:#C8F135; line-height:1; min-width:60px;
  text-align:right;
}}
.card-body {{ flex:1; }}
.card-title {{
  font-family:var(--font-body); font-weight:700;
  font-size:30px; color:#FFFFFF;
  margin-bottom:6px;
}}
.card-desc {{
  font-family:var(--font-body); font-size:22px;
  color:rgba(255,255,255,0.55);
}}
.anchor {{
  margin-top:44px;
  font-family:var(--font-title); font-size:38px;
  color:#C8F135; letter-spacing:2px; text-transform:uppercase;
}}
.handle {{
  position:absolute; bottom:20px; right:56px;
  font-size:20px; color:rgba(255,255,255,0.3);
  font-family:var(--font-body);
}}
</style></head><body>
  <div class="bg"></div>
  <div class="eyebrow">o que você vai encontrar</div>
  <div class="logo">CAFÉ COM TÊNIS</div>
  <div class="content">
    <div class="section-title">PARTE <span>02</span></div>
    <div class="cards">
      <div class="card">
        <div class="card-num">04</div>
        <div class="card-body">
          <div class="card-title">João Fonseca e Bia Haddad — cobertura total</div>
          <div class="card-desc">Cada ponto deles, com análise</div>
        </div>
      </div>
      <div class="card">
        <div class="card-num">05</div>
        <div class="card-body">
          <div class="card-title">Curiosidades históricas que você não sabia</div>
          <div class="card-desc">Tênis tem 150 anos de história. Vamos usar tudo.</div>
        </div>
      </div>
      <div class="card">
        <div class="card-num">06</div>
        <div class="card-body">
          <div class="card-title">Polêmicas, bastidores e o que a mídia não conta</div>
          <div class="card-desc">O tour tem muito mais do que o placar</div>
        </div>
      </div>
    </div>
    <div class="anchor">ATP + WTA. Todo dia. Sem perder nada.</div>
  </div>
  <div class="handle">@cafecomteniss</div>
</body></html>"""


# ── Slide 5 — Autoridade via Fonseca stat ───────────────────────────────────

def slide_05() -> str:
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
{BRAND_KIT}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  width:1080px; height:1080px;
  background:#0A0A0A;
  font-family:var(--font-body);
  overflow:hidden; position:relative;
}}
.bg {{
  position:absolute; inset:0;
  {_bg("fonseca_action2", "center 25%")}
}}
.grad {{
  position:absolute; inset:0;
  background:linear-gradient(
    to top,
    rgba(10,10,10,1.0) 0%,
    rgba(10,10,10,0.88) 40%,
    rgba(10,10,10,0.45) 70%,
    rgba(10,10,10,0.15) 100%
  );
}}
.tag {{
  position:absolute; top:52px; left:52px;
  background:#C8F135; color:#0A0A0A;
  font-family:var(--font-body); font-weight:700;
  font-size:18px; letter-spacing:3px; text-transform:uppercase;
  padding:8px 22px; border-radius:4px;
}}
.logo {{
  position:absolute; top:52px; right:52px;
  color:#C8F135; font-family:var(--font-title);
  font-size:28px; letter-spacing:1px;
}}
.content {{
  position:absolute; bottom:0; left:0; right:0;
  padding:0 56px 64px;
}}
.eyebrow {{
  font-family:var(--font-body); font-weight:700;
  font-size:20px; letter-spacing:3px; text-transform:uppercase;
  color:#C8F135; margin-bottom:16px;
}}
.big-number {{
  font-family:var(--font-title); font-size:220px; line-height:0.85;
  color:#FFFFFF; letter-spacing:-4px;
  text-shadow:0 0 60px rgba(200,241,53,0.25);
}}
.big-label {{
  font-family:var(--font-title); font-size:62px; line-height:1;
  color:#C8F135; letter-spacing:3px; text-transform:uppercase;
  margin-bottom:32px;
}}
.comparison {{
  display:flex; gap:40px; margin-top:8px;
}}
.comp-item {{
  display:flex; flex-direction:column; gap:4px;
}}
.comp-name {{
  font-family:var(--font-body); font-weight:700;
  font-size:22px; color:rgba(255,255,255,0.9);
}}
.comp-detail {{
  font-family:var(--font-body); font-size:19px;
  color:rgba(255,255,255,0.45);
}}
.comp-item.highlight .comp-name {{ color:#C8F135; }}
.divider-v {{ width:1px; background:rgba(255,255,255,0.2); }}
.footnote {{
  margin-top:28px;
  font-family:var(--font-body); font-size:22px;
  color:rgba(255,255,255,0.50); font-style:italic;
}}
.handle {{
  position:absolute; bottom:20px; right:56px;
  font-size:20px; color:rgba(255,255,255,0.3);
  font-family:var(--font-body);
}}
</style></head><body>
  <div class="bg"></div>
  <div class="grad"></div>
  <div class="tag">joão fonseca</div>
  <div class="logo">CAFÉ COM TÊNIS</div>
  <div class="content">
    <div class="eyebrow">o que esse canal vai cobrir</div>
    <div class="big-number">19</div>
    <div class="big-label">anos. Top 29 do mundo.</div>
    <div class="comparison">
      <div class="comp-item highlight">
        <div class="comp-name">Fonseca — 19 anos</div>
        <div class="comp-detail">Top 29 ATP · 2025</div>
      </div>
      <div class="divider-v"></div>
      <div class="comp-item">
        <div class="comp-name">Nadal — chegou top 30 com 21</div>
        <div class="comp-detail">2 anos mais velho</div>
      </div>
      <div class="divider-v"></div>
      <div class="comp-item">
        <div class="comp-name">Djokovic — com 20</div>
        <div class="comp-detail">1 ano mais velho</div>
      </div>
    </div>
    <div class="footnote">Esse é o tipo de dado que você vai encontrar aqui. Todo dia.</div>
  </div>
  <div class="handle">@cafecomteniss</div>
</body></html>"""


# ── Slide 6 — Roland Garros urgência ────────────────────────────────────────

def slide_06() -> str:
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
{BRAND_KIT}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  width:1080px; height:1080px;
  background:#0A0A0A;
  font-family:var(--font-body);
  overflow:hidden; position:relative;
}}
.bg {{
  position:absolute; inset:0;
  {_bg("alcaraz_action", "center 20%")}
}}
.grad {{
  position:absolute; inset:0;
  background:linear-gradient(
    to top,
    rgba(10,10,10,1.0) 0%,
    rgba(10,10,10,0.75) 40%,
    rgba(10,10,10,0.45) 70%,
    rgba(10,10,10,0.20) 100%
  );
}}
/* Clay tint overlay */
.clay {{
  position:absolute; inset:0;
  background:rgba(180,70,20,0.12);
}}
.tag {{
  position:absolute; top:52px; left:52px;
  background:rgba(180,70,20,0.85); color:#FFFFFF;
  font-family:var(--font-body); font-weight:700;
  font-size:18px; letter-spacing:3px; text-transform:uppercase;
  padding:8px 22px; border-radius:4px;
}}
.logo {{
  position:absolute; top:52px; right:52px;
  color:#C8F135; font-family:var(--font-title);
  font-size:28px; letter-spacing:1px;
}}
.content {{
  position:absolute; bottom:0; left:0; right:0;
  padding:0 56px 64px;
}}
.countdown {{
  font-family:var(--font-title); font-size:160px; line-height:0.88;
  color:#C8F135; letter-spacing:-2px;
  text-shadow:0 0 60px rgba(200,241,53,0.30);
}}
.countdown-label {{
  font-family:var(--font-title); font-size:48px;
  color:rgba(255,255,255,0.75); letter-spacing:3px;
  text-transform:uppercase; margin-bottom:32px;
}}
.tournament {{
  font-family:var(--font-title); font-size:80px; line-height:0.95;
  color:#FFFFFF; text-transform:uppercase; letter-spacing:2px;
  margin-bottom:28px;
  text-shadow:2px 4px 20px rgba(0,0,0,0.9);
}}
.names {{
  font-family:var(--font-body); font-weight:700;
  font-size:26px; color:rgba(255,255,255,0.65);
  letter-spacing:2px; margin-bottom:24px;
}}
.names span {{ color:#C8F135; }}
.cta {{
  font-family:var(--font-body); font-weight:700;
  font-size:28px; color:#FFFFFF;
  border-left:4px solid #C8F135; padding-left:18px;
}}
.handle {{
  position:absolute; bottom:20px; right:56px;
  font-size:20px; color:rgba(255,255,255,0.3);
  font-family:var(--font-body);
}}
</style></head><body>
  <div class="bg"></div>
  <div class="grad"></div>
  <div class="clay"></div>
  <div class="tag">roland garros</div>
  <div class="logo">CAFÉ COM TÊNIS</div>
  <div class="content">
    <div class="countdown">16</div>
    <div class="countdown-label">dias para o maior Grand Slam da temporada</div>
    <div class="tournament">ROLAND<br>GARROS</div>
    <div class="names"><span>Fonseca</span> · Alcaraz · Sinner · Swiatek</div>
    <div class="cta">Você precisa estar aqui antes disso começar.</div>
  </div>
  <div class="handle">@cafecomteniss</div>
</body></html>"""


# ── Slide 7 — Como funciona ──────────────────────────────────────────────────

def slide_07() -> str:
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
{BRAND_KIT}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  width:1080px; height:1080px;
  background:#0A0A0A;
  font-family:var(--font-body);
  overflow:hidden; position:relative;
}}
.logo {{
  position:absolute; top:52px; right:52px;
  color:#C8F135; font-family:var(--font-title);
  font-size:28px; letter-spacing:1px;
}}
.content {{
  position:absolute;
  top:50%; left:56px; right:56px;
  transform:translateY(-50%);
}}
.headline {{
  font-family:var(--font-title);
  font-size:86px; line-height:0.92;
  color:#FFFFFF; text-transform:uppercase;
  letter-spacing:2px; margin-bottom:16px;
}}
.headline span {{ color:#C8F135; }}
.tagline {{
  font-family:var(--font-body); font-weight:700;
  font-size:26px; color:rgba(255,255,255,0.45);
  letter-spacing:1px; margin-bottom:60px;
}}
.steps {{
  display:flex; flex-direction:column; gap:0;
}}
.step {{
  display:flex; align-items:center; gap:32px;
  padding:28px 0;
  border-bottom:1px solid rgba(255,255,255,0.08);
}}
.step:last-child {{ border-bottom:none; }}
.step-num {{
  width:72px; height:72px; min-width:72px;
  border:2px solid #C8F135; border-radius:50%;
  display:flex; align-items:center; justify-content:center;
  font-family:var(--font-title); font-size:44px;
  color:#C8F135; line-height:1;
}}
.step-body {{ flex:1; }}
.step-title {{
  font-family:var(--font-body); font-weight:700;
  font-size:32px; color:#FFFFFF; margin-bottom:6px;
}}
.step-desc {{
  font-family:var(--font-body); font-size:22px;
  color:rgba(255,255,255,0.45);
}}
.step-desc span {{ color:#C8F135; font-weight:700; }}
.handle {{
  position:absolute; bottom:20px; right:56px;
  font-size:20px; color:rgba(255,255,255,0.3);
  font-family:var(--font-body);
}}
</style></head><body>
  <div class="logo">CAFÉ COM TÊNIS</div>
  <div class="content">
    <div class="headline">30<br><span>SEGUNDOS.</span></div>
    <div class="tagline">Para nunca mais perder nada do tour.</div>
    <div class="steps">
      <div class="step">
        <div class="step-num">1</div>
        <div class="step-body">
          <div class="step-title">Segue <span style="color:#C8F135">@cafecomteniss</span></div>
          <div class="step-desc">Instagram · agora mesmo</div>
        </div>
      </div>
      <div class="step">
        <div class="step-num">2</div>
        <div class="step-body">
          <div class="step-title">Ativa as notificações</div>
          <div class="step-desc">Sininho → <span>Todos os posts</span></div>
        </div>
      </div>
      <div class="step">
        <div class="step-num">3</div>
        <div class="step-body">
          <div class="step-title">Nunca mais fica por fora</div>
          <div class="step-desc">ATP · WTA · Breaking · Análises · Fonseca</div>
        </div>
      </div>
    </div>
  </div>
  <div class="handle">@cafecomteniss</div>
</body></html>"""


# ── Slide 8 — CTA Final ─────────────────────────────────────────────────────

def slide_08() -> str:
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
{BRAND_KIT}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  width:1080px; height:1080px;
  background:#0A0A0A;
  font-family:var(--font-body);
  overflow:hidden; position:relative;
  display:flex; align-items:center; justify-content:center;
}}
/* Subtle grid texture */
.grid {{
  position:absolute; inset:0;
  background-image:
    linear-gradient(rgba(200,241,53,0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(200,241,53,0.03) 1px, transparent 1px);
  background-size:54px 54px;
}}
/* Lime glow at center */
.glow {{
  position:absolute;
  top:50%; left:50%; transform:translate(-50%,-50%);
  width:600px; height:600px;
  background:radial-gradient(circle, rgba(200,241,53,0.08) 0%, transparent 70%);
}}
.center {{
  position:relative; z-index:1;
  display:flex; flex-direction:column;
  align-items:center; text-align:center;
  gap:0;
}}
.logo-big {{
  font-family:var(--font-title); font-size:96px;
  color:#C8F135; letter-spacing:4px; text-transform:uppercase;
  line-height:1; margin-bottom:4px;
}}
.tagline {{
  font-family:var(--font-body); font-weight:700;
  font-size:22px; letter-spacing:4px; text-transform:uppercase;
  color:rgba(255,255,255,0.35); margin-bottom:64px;
}}
.cta-main {{
  font-family:var(--font-title); font-size:68px;
  color:#FFFFFF; text-transform:uppercase;
  letter-spacing:2px; line-height:1.0;
  margin-bottom:28px;
}}
.cta-main span {{ color:#C8F135; }}
.cta-sub {{
  font-family:var(--font-body); font-size:28px;
  color:rgba(255,255,255,0.55);
  max-width:700px; line-height:1.5;
  margin-bottom:60px;
}}
.handle-big {{
  font-family:var(--font-title); font-size:56px;
  color:#C8F135; letter-spacing:2px;
  border:2px solid rgba(200,241,53,0.35);
  padding:16px 48px; border-radius:8px;
}}
</style></head><body>
  <div class="grid"></div>
  <div class="glow"></div>
  <div class="center">
    <div class="logo-big">CAFÉ COM TÊNIS</div>
    <div class="tagline">ATP · WTA · Em Português</div>
    <div class="cta-main">O TOUR NÃO<br><span>ESPERA.</span></div>
    <div class="cta-sub">Você vai acompanhar com ou sem dados.<br>Prefere com.</div>
    <div class="handle-big">@cafecomteniss</div>
  </div>
</body></html>"""


# ── Copy (caption + Meta Ads) ────────────────────────────────────────────────

CAPTION = """Tênis de verdade. Em português. Com dados.

Somos o @cafecomteniss — canal de tênis ATP + WTA em português. Breaking results, estatísticas reais, análises de jogo, bastidores do tour e cobertura total dos brasileiros João Fonseca e Bia Haddad.

Sem rosto. Sem filtro. A autoridade vem dos dados.

Roland Garros começa em 16 dias. Fonseca, Alcaraz, Sinner e Swiatek no mesmo Grand Slam. Esse é o melhor momento do ano para você decidir: quer acompanhar com contexto ou sem?

Ativa o sininho e nunca mais fica por fora."""

HASHTAGS = [
    "#tenis", "#tennis", "#ATP", "#WTA", "#rolandgarros",
    "#joaofonseca", "#fonseca", "#alcaraz", "#sinner", "#swiatek",
    "#tenisbrasileiro", "#tenisaovivo", "#cafecomtenis", "#cafecomteniss",
    "#grandslam", "#tenisargentina", "#tenismundial", "#tenisfeminino",
    "#sportstenis", "#biaHaddad",
]

AD_COPIES = {
    "A_emocional": {
        "headline": "Tênis em português. De verdade.",
        "texto_primario": "Você assiste às 3h da manhã e não tem quem analise depois. Agora tem.",
        "descricao": "Segue e ativa o sininho.",
        "angulo": "Identificação com a dor do fã de tênis no Brasil",
    },
    "B_racional": {
        "headline": "Stats de tênis que ninguém faz em PT",
        "texto_primario": "H2H reais, análises táticas e breaking results antes de qualquer canal em português.",
        "descricao": "Acompanhe com inteligência.",
        "angulo": "Autoridade técnica — dados e cobertura séria",
    },
    "C_fonseca": {
        "headline": "Fonseca. Top 29. 19 anos.",
        "texto_primario": "Roland Garros começa em 16 dias. Cobertura completa do melhor tenista BR de uma geração.",
        "descricao": "Não perde nenhum jogo dele.",
        "angulo": "Urgência Fonseca + Roland Garros — menor CPF esperado",
    },
}

ADS_STRATEGY = """
ESTRATÉGIA META ADS — @cafecomteniss
=====================================

Orçamento: R$40/dia × 7 dias = R$280 total
Objetivo: Engajamento com perfil (seguir)
Formato: Carrossel (os 8 slides)
Público: Brasil · 18-45 anos
Interesses: Tennis, ATP World Tour, WTA, Roland Garros, João Fonseca, ESPN Brasil

LÓGICA DO A/B TEST:
- Roda as 3 versões de copy em paralelo (R$13/dia cada)
- Dia 3: pausa versões com CPF > R$2,00
- Dia 5: escala a versão com CPF < R$1,00
- Com Roland Garros chegando, o interesse orgânico amplifica o pago

META: 1.000 seguidores pagos na primeira semana
CPF-alvo: < R$1,50 nas versões de Fonseca/emocional

TIMING IDEAL:
- Publicar feed: agora (May 9)
- Subir anúncio: amanhã manhã (May 10) — 15 dias antes de RG
- Peak de interesse: May 22-25 (semana de abertura)
"""


# ── Runner ───────────────────────────────────────────────────────────────────

SLIDES = [
    ("slide_01_hook",        slide_01),
    ("slide_02_problema",    slide_02),
    ("slide_03_conteudo_1",  slide_03),
    ("slide_04_conteudo_2",  slide_04),
    ("slide_05_fonseca",     slide_05),
    ("slide_06_roland",      slide_06),
    ("slide_07_como",        slide_07),
    ("slide_08_cta",         slide_08),
]


async def run():
    paths = []

    for name, fn in SLIDES:
        out = str(OUTPUT_DIR / f"{name}.png")
        html = fn()
        result = html_to_png(html, out, 1080, 1080)
        if result:
            log.info(f"✓ {name}.png")
            paths.append(result)
        else:
            log.error(f"✗ {name} — falhou na renderização")

    # Salvar copy
    copy_path = OUTPUT_DIR / "launch_post_copy.txt"
    with open(copy_path, "w", encoding="utf-8") as f:
        f.write("=== CAPTION ===\n\n")
        f.write(CAPTION + "\n\n")
        f.write(" ".join(HASHTAGS) + "\n\n")
        f.write("=== META ADS A/B ===\n\n")
        for version, data in AD_COPIES.items():
            f.write(f"--- VERSÃO {version} ---\n")
            f.write(f"Headline ({len(data['headline'])} chars): {data['headline']}\n")
            f.write(f"Texto primário ({len(data['texto_primario'])} chars): {data['texto_primario']}\n")
            f.write(f"Descrição ({len(data['descricao'])} chars): {data['descricao']}\n")
            f.write(f"Ângulo: {data['angulo']}\n\n")
        f.write(ADS_STRATEGY)

    log.info(f"Copy salvo: {copy_path}")
    log.info(f"Slides gerados: {len(paths)}/8")

    if len(paths) < 8:
        log.warning("Nem todos os slides foram gerados — verifique os erros acima")
        return paths

    # Publicar
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
            has_ig = bool(resp.get("instagram_business_account"))
        else:
            has_ig = False
    except Exception:
        has_ig = False

    caption_full = CAPTION + "\n\n" + " ".join(HASHTAGS)

    if has_ig:
        from publisher.graph_publisher import GraphPublisher
        publisher = GraphPublisher()
        log.info("Publicando carrossel no Instagram via Graph API...")
        ok = await publisher.publish_carousel(paths, caption_full)
        if ok:
            log.info("Carrossel de lançamento publicado no Instagram!")
        else:
            log.error("Publicação falhou — slides salvos em output/launch_post/")
    else:
        log.info("Meta API não configurada — slides salvos localmente em output/launch_post/")
        log.info("Para publicar: use o Meta Business Suite ou suba manualmente")

    return paths


if __name__ == "__main__":
    asyncio.run(run())
