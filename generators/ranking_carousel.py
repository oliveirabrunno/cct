"""
Ranking Carousel — gera 2 slides 1080×1350 (ATP + WTA) com o template ranking.html.

Pipeline:
  1. Busca top 30 ao vivo via live-tennis.eu
  2. Compara com cache da semana anterior (por nome) para calcular change real
  3. Injeta JSON no ranking.html e tira screenshot com Puppeteer
  4. Busca foto do vencedor do torneio mais recente (com troféu se possível)
  5. Claude gera o resumo textual da semana
  6. Retorna dict com image_paths, caption, hashtags

Bug history:
  - 2026-05-13: campo `move` de live-tennis.eu NÃO é variação de posição
    (sempre positivo / representa outro índice interno). Fix: usar cache diff.
"""

import json
import re
import subprocess
import time
from datetime import date, datetime
from pathlib import Path

from generators.content import ContentGenerator, _load_prompt
from utils.image_manager import ImageManager
from utils.logger import get_logger

log = get_logger(__name__)

OUTPUT_DIR   = Path("output/queue")
CACHE_DIR    = Path("data")
TEMPLATE     = Path("config/templates/ranking.html")
SCREENSHOT_JS = Path("generators/screenshot.js")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Mapa de código de país → emoji de bandeira
COUNTRY_FLAGS: dict[str, str] = {
    "ITA": "🇮🇹", "ESP": "🇪🇸", "GER": "🇩🇪", "SRB": "🇷🇸", "RUS": "🇷🇺",
    "USA": "🇺🇸", "NOR": "🇳🇴", "AUS": "🇦🇺", "GRE": "🇬🇷", "POL": "🇵🇱",
    "DEN": "🇩🇰", "GBR": "🇬🇧", "FRA": "🇫🇷", "CAN": "🇨🇦", "BRA": "🇧🇷",
    "ARG": "🇦🇷", "CHI": "🇨🇱", "KAZ": "🇰🇿", "CZE": "🇨🇿", "BUL": "🇧🇬",
    "KOR": "🇰🇷", "JPN": "🇯🇵", "CHN": "🇨🇳", "RSA": "🇿🇦", "NED": "🇳🇱",
    "SUI": "🇨🇭", "AUT": "🇦🇹", "BEL": "🇧🇪", "CRO": "🇭🇷", "HUN": "🇭🇺",
    "ROU": "🇷🇴", "UKR": "🇺🇦", "BLR": "🇧🇾", "GEO": "🇬🇪", "MDA": "🇲🇩",
    "TUN": "🇹🇳", "EGY": "🇪🇬", "MAR": "🇲🇦", "BOL": "🇧🇴", "URU": "🇺🇾",
    "PAR": "🇵🇾", "COL": "🇨🇴", "MEX": "🇲🇽", "DOM": "🇩🇴",
}


def _flag(country: str) -> str:
    return COUNTRY_FLAGS.get(country.upper(), "🏳️")


def _surface_for_date(today: date = None) -> str:
    """Detecta superfície dominante do calendário pelo mês."""
    m = (today or date.today()).month
    if m in (5, 6):   return "clay"
    if m in (7,):      return "grass"
    return "hard"


def _load_cache(tour: str) -> list[dict]:
    path = CACHE_DIR / f"ranking_cache_{tour.lower()}.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return []


def _save_cache(tour: str, players: list[dict]) -> None:
    path = CACHE_DIR / f"ranking_cache_{tour.lower()}.json"
    path.write_text(json.dumps(players, ensure_ascii=False, indent=2))


def _calc_change(curr_rank: int, prev_players: list[dict]) -> int | None:
    """
    Calcula mudança de posição vs semana anterior.
    Retorna None se o jogador é novo no top 30.
    """
    for p in prev_players:
        if p.get("rank") == curr_rank:
            return None  # não conseguimos identificar pelo rank, precisaria por nome
    return None


def build_ranking_data(tour: str, top_n: int = 30) -> tuple[list[dict], list[dict]]:
    """
    Busca o ranking atual e calcula change comparando com cache da semana anterior.

    Change = prev_rank - curr_rank
      > 0  → subiu (badge verde)  ex: estava #8, agora #5  → +3
      < 0  → caiu  (badge vermelho) ex: estava #5, agora #8  → -3
      = 0  → estável (traço)
      None → novo no top 30 (badge NEW)

    IMPORTANTE: NÃO usa o campo `move` de live-tennis.eu — esse campo
    é um índice interno do site, sempre positivo, não representa variação real.
    """
    from scrapers.live_ranking import fetch_atp_live_rankings, fetch_wta_live_rankings

    prev = _load_cache(tour)

    if tour.upper() == "ATP":
        raw = fetch_atp_live_rankings(top_n)
    else:
        raw = fetch_wta_live_rankings(top_n)

    # Construir lookup: nome normalizado → rank da semana passada
    def _norm(name: str) -> str:
        return name.lower().strip()

    prev_lookup: dict[str, int] = {_norm(p["name"]): p["rank"] for p in prev}
    prev_names = set(prev_lookup.keys())
    has_prev = bool(prev)

    players = []
    for p in raw[:top_n]:
        curr_rank  = p["rank"]
        name_norm  = _norm(p["name"])

        if not has_prev:
            # Primeira execução: sem histórico — mostrar traço (0) para todos
            change = 0
        elif name_norm not in prev_names:
            # Estava fora do top 30 na semana passada → NEW
            change = None
        else:
            # prev_rank - curr_rank: positivo = subiu, negativo = caiu
            prev_rank = prev_lookup[name_norm]
            change = prev_rank - curr_rank

        players.append({
            "rank":    curr_rank,
            "name":    p["name"],
            "country": p.get("country", ""),
            "flag":    _flag(p.get("country", "")),
            "points":  p["points"],
            "change":  change,
        })

    # Salvar cache com ranking desta semana (base para comparação na próxima)
    _save_cache(tour, [{"name": p["name"], "rank": p["rank"]} for p in players])

    return players, prev


def find_movers(players: list[dict]) -> dict:
    """
    Identifica os destaques da semana: maiores subidas, quedas e estreantes.
    """
    risers  = sorted([p for p in players if (p["change"] or 0) > 0],
                     key=lambda x: -(x["change"] or 0))
    fallers = sorted([p for p in players if (p["change"] or 0) < 0],
                     key=lambda x: (x["change"] or 0))
    newbies = [p for p in players if p["change"] is None]

    return {
        "top_riser":  risers[0]  if risers  else None,
        "top_faller": fallers[0] if fallers else None,
        "newbies":    newbies,
        "risers":     risers[:3],
        "fallers":    fallers[:3],
    }


def _image_to_base64(filepath: str) -> str:
    import base64
    path = Path(filepath)
    if not path.exists():
        return ""
    ext  = path.suffix.lower().strip(".")
    mime = "image/png" if ext == "png" else ("image/webp" if ext == "webp" else "image/jpeg")
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:{mime};base64,{b64}"


async def _fetch_tournament_winner_photo(tour: str, tournament_name: str) -> tuple[str, str, str]:
    """
    Busca foto do vencedor do torneio mais recente com troféu.
    Estratégia:
      1. Tenta detectar vencedor recente via Flashscore (match finalizado de torneio grande)
      2. Busca imagem com query específica: '{winner} {tournament} trophy'
      3. Fallback: #1 do ranking
    Retorna (base64_image, credit_text, winner_name).
    """
    img_manager = ImageManager()
    winner_name = None

    # Tentar descobrir vencedor real via Flashscore
    try:
        from scrapers.flashscore import get_recent_tournament_winner
        winner_name = await get_recent_tournament_winner(tour)
        if winner_name:
            log.info(f"Vencedor recente ({tour}): {winner_name}")
    except Exception as e:
        log.debug(f"Flashscore winner lookup falhou: {e}")

    # Fallback: #1 do ranking
    if not winner_name:
        try:
            from scrapers.live_ranking import fetch_atp_live_rankings, fetch_wta_live_rankings
            top = fetch_atp_live_rankings(1) if tour.upper() == "ATP" else fetch_wta_live_rankings(1)
            winner_name = top[0]["name"] if top else ("Jannik Sinner" if tour.upper() == "ATP" else "Aryna Sabalenka")
        except Exception:
            winner_name = "Jannik Sinner" if tour.upper() == "ATP" else "Aryna Sabalenka"

    # Buscar foto com query de troféu específico do torneio
    trophy_queries = [
        f"{winner_name} {tournament_name} trophy",
        f"{winner_name} {tournament_name} winner",
        f"{winner_name} trophy",
        winner_name,
    ]

    for query in trophy_queries:
        try:
            img_data = await img_manager.get_player_image(
                winner_name,
                image_type="trophy",
                search_override=query,
            )
            if img_data and img_data.get("path"):
                b64    = _image_to_base64(img_data["path"])
                credit = img_data.get("credit_text", "ATP Tour") or "ATP Tour"
                log.info(f"Foto troféu ({tour}): {winner_name} | query: '{query}'")
                return b64, credit, winner_name
        except Exception as e:
            log.debug(f"Falha query '{query}': {e}")
            continue

    log.warning(f"Sem foto de troféu para {tour} — usando cache genérico")
    return "", f"{tour} Tour", winner_name


def _generate_slide_html(
    tour: str,
    players: list[dict],
    image_b64: str,
    credit: str,
    winner_name: str,
    surface: str,
    tournament_name: str,
    updated_at: str,
) -> str:
    """
    Injeta os dados no ranking.html e retorna o HTML pronto para screenshot.
    """
    template = TEMPLATE.read_text(encoding="utf-8")

    ranking_json = {
        "tour":       tour.upper(),
        "surface":    surface,
        "tournament": tournament_name,
        "updatedAt":  updated_at,
        "image":      image_b64,
        "credit":     credit,
        "kicker":     f"Ranking {tour.upper()} · Semana {updated_at}",
        "title_winner": winner_name.split()[-1],
        "players":    players,
    }

    json_str = json.dumps(ranking_json, ensure_ascii=False)
    html = re.sub(
        r'<script id="ranking-data" type="application/json">.*?</script>',
        f'<script id="ranking-data" type="application/json">\n{json_str}\n</script>',
        template,
        flags=re.DOTALL,
    )
    return html


def _html_to_png(html: str, output_path: str) -> str | None:
    """Screenshot 1080×1350 via Puppeteer."""
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as f:
        f.write(html)
        tmp = f.name

    try:
        result = subprocess.run(
            ["node", str(SCREENSHOT_JS), tmp, output_path, "1080", "1350"],
            capture_output=True, text=True, timeout=40,
        )
        if result.returncode != 0:
            log.error(f"Puppeteer erro: {result.stderr}")
            return None
        log.info(f"Ranking slide gerado: {output_path}")
        return output_path
    except Exception as e:
        log.error(f"_html_to_png falhou: {e}")
        return None
    finally:
        try: os.unlink(tmp)
        except: pass


def _generate_caption(tour: str, players: list[dict], movers: dict, tournament_name: str) -> tuple[str, list[str]]:
    """
    Claude gera resumo da semana em ~120 palavras.
    """
    try:
        content_gen = ContentGenerator()
        prompt_tpl  = _load_prompt("ranking_week") or ""

        # Serializar destaques para o prompt
        riser_text  = ""
        faller_text = ""
        newbie_text = ""

        if movers["top_riser"]:
            r = movers["top_riser"]
            riser_text = f"{r['name']} (#{r['rank']}, +{r['change']} posições)"

        if movers["top_faller"]:
            f = movers["top_faller"]
            faller_text = f"{f['name']} (#{f['rank']}, {f['change']} posições)"

        if movers["newbies"]:
            newbie_text = ", ".join(f"{p['name']} (#{p['rank']})" for p in movers["newbies"][:3])

        top5 = "\n".join(
            f"#{p['rank']} {p['name']} — {p['points']} pts" for p in players[:5]
        )

        prompt = (prompt_tpl
            .replace("{tour}", tour.upper())
            .replace("{tournament}", tournament_name)
            .replace("{top5}", top5)
            .replace("{top_riser}", riser_text or "Sem grandes subidas")
            .replace("{top_faller}", faller_text or "Sem grandes quedas")
            .replace("{newbies}", newbie_text or "Nenhum estreante")
            .replace("{updated_at}", date.today().strftime("%d/%m/%Y"))
        )

        system = _load_prompt("base_voice") or ""
        raw    = content_gen._call_claude(system, prompt, max_tokens=512)
        data   = content_gen._parse_json_response(raw)

        if data:
            caption  = data.get("caption", "")
            hashtags = re.findall(r"#[a-zA-ZÀ-ÿ]\w*", caption)
            caption  = re.compile(r"#[a-zA-ZÀ-ÿ]\w*").sub("", caption).strip()
            return caption, hashtags

    except Exception as e:
        log.error(f"Claude caption falhou: {e}")

    # Fallback sem Claude
    top3 = ", ".join(f"#{p['rank']} {p['name'].split()[-1]}" for p in players[:3])
    return (
        f"Ranking {tour.upper()} atualizado 🎾\n\nTop 3: {top3}\n\nSegue @cafecomteniss.",
        [f"#{tour}Tennis", "#Tenis", "#Tennis", "#CafeComTenis", "#Ranking"],
    )


async def generate_ranking_carousel(
    tournament_name: str = None,
    surface: str = None,
) -> dict | None:
    """
    Ponto de entrada principal.
    Retorna dict com image_paths, caption, hashtags.
    """
    today       = date.today()
    updated_at  = today.strftime("%d.%m.%Y")
    surface     = surface or _surface_for_date(today)
    tournament_name = tournament_name or _guess_tournament(today)

    image_paths = []

    for tour in ("ATP", "WTA"):
        log.info(f"=== Gerando slide {tour} ===")
        players, prev = build_ranking_data(tour, top_n=30)

        if not players:
            log.error(f"Sem dados de ranking para {tour}")
            continue

        movers   = find_movers(players)
        b64, credit, winner = await _fetch_tournament_winner_photo(tour, tournament_name)

        html = _generate_slide_html(
            tour        = tour,
            players     = players,
            image_b64   = b64,
            credit      = credit,
            winner_name = winner,
            surface     = surface,
            tournament_name = tournament_name,
            updated_at  = updated_at,
        )

        ts  = int(time.time())
        out = str(OUTPUT_DIR / f"ranking_{tour.lower()}_{ts}.png")
        png = _html_to_png(html, out)
        if png:
            image_paths.append(png)

    if not image_paths:
        return None

    # Caption da ATP (mais relevante para o público)
    players_atp, _ = build_ranking_data("ATP", 30)
    movers_atp     = find_movers(players_atp)
    caption, hashtags = _generate_caption("ATP", players_atp, movers_atp, tournament_name)

    # Adicionar WTA no caption
    players_wta, _ = build_ranking_data("WTA", 30)
    movers_wta     = find_movers(players_wta)
    wta_caption, wta_tags = _generate_caption("WTA", players_wta, movers_wta, tournament_name)
    full_caption = f"{caption}\n\n🎾 WTA:\n{wta_caption}"

    all_tags = list(dict.fromkeys(hashtags + wta_tags + ["#Ranking", "#ATP", "#WTA", "#CafeComTenis"]))

    log.info(f"Ranking carousel: {len(image_paths)} slides | {len(players_atp)} jogadores ATP | {len(players_wta)} jogadores WTA")
    return {
        "image_paths": image_paths,
        "caption":     full_caption,
        "hashtags":    all_tags,
        "movers_atp":  movers_atp,
        "movers_wta":  movers_wta,
    }


def _guess_tournament(today: date) -> str:
    """Adivinha o torneio atual pelo calendário."""
    m, d = today.month, today.day
    if m == 5 and d < 20:   return "Roma Masters"
    if m == 5 and d >= 20:  return "Roland Garros"
    if m == 6 and d < 9:    return "Roland Garros"
    if m == 6 and d < 25:   return "Queen's / Halle"
    if m == 7 and d < 15:   return "Wimbledon"
    if m == 8:              return "Cincinnati / Rogers Cup"
    if m == 9:              return "US Open"
    if m == 10:             return "Shanghai / Pequim"
    if m == 11:             return "Paris Masters / WTA Finals"
    return "ATP Tour"
