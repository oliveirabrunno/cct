"""
ATP IQ powered by dados reais — H2H, surface performance, stats de saque.

Substitui os dados mockados por dados calculados via Sackmann CSV e scraping.
"""

from utils.logger import get_logger
from generators.chart import generate_bar_chart, generate_radar_chart
from scrapers.stats_scraper import (
    get_h2h,
    get_surface_record,
    get_serve_stats,
    get_atp_stat_leaders,
)
from datetime import date

log = get_logger(__name__)

CURRENT_YEAR = date.today().year


def get_shocking_stat(player_name: str, tournament_name: str = None) -> dict:
    """
    Retorna a estatística mais impactante do jogador para um post.
    Tenta (em ordem): serve stats → surface record → fallback simples.
    """
    # Detectar superfície do torneio atual
    surface = _detect_surface(tournament_name)

    # 1. Stats de saque no piso atual
    try:
        srv = get_serve_stats(player_name, year=CURRENT_YEAR, surface=surface)
        if srv.get("matches_analyzed", 0) >= 3:
            chart_path = _build_serve_chart(player_name, srv)
            return {
                "headline": _serve_headline(srv),
                "subtext":  srv["insight"],
                "chart_path": chart_path,
                "stat_type": "serve",
                "raw": srv,
            }
    except Exception as e:
        log.debug(f"get_serve_stats falhou para {player_name}: {e}")

    # 2. Surface record
    try:
        rec = get_surface_record(player_name, year=CURRENT_YEAR)
        surf_key = surface or "hard"
        surf_data = rec.get(surf_key, {})
        if surf_data.get("total", 0) >= 3:
            chart_path = _build_surface_chart(player_name, rec)
            return {
                "headline": f"{surf_data['wins']}-{surf_data['losses']} ({surf_data['pct']}) no {surf_key.capitalize()}",
                "subtext":  rec["insight"],
                "chart_path": chart_path,
                "stat_type": "surface",
                "raw": rec,
            }
    except Exception as e:
        log.debug(f"get_surface_record falhou para {player_name}: {e}")

    # 3. Fallback sem gráfico
    short = player_name.split()[-1]
    return {
        "headline": f"{short} em destaque",
        "subtext":  f"Acompanhe a performance de {player_name} no torneio.",
        "chart_path": None,
        "stat_type": "fallback",
        "raw": {},
    }


def get_h2h_card(player_a: str, player_b: str, tournament_name: str = None) -> dict:
    """
    Gera dados completos de H2H para um card pré-jogo.
    Inclui contexto histórico do mesmo torneio se disponível.
    """
    from scrapers.match_scout import get_same_tournament_h2h

    surface = _detect_surface(tournament_name)
    h2h     = get_h2h(player_a, player_b, surface=surface)

    # Contexto do mesmo torneio (ex: "Roland Garros 2025: Sinner venceu 6-4 7-5")
    tourn_ctx = None
    if tournament_name:
        try:
            tourn_ctx = get_same_tournament_h2h(player_a, player_b, tournament_name)
        except Exception as e:
            log.debug(f"get_same_tournament_h2h falhou: {e}")

    subtext = h2h["insight"]
    if tourn_ctx:
        subtext = f"{h2h['insight']}\n{tourn_ctx['context_text']}"

    chart_path = _build_h2h_chart(h2h)

    return {
        "headline": f"H2H: {player_a.split()[-1].upper()} vs {player_b.split()[-1].upper()}",
        "subtext":  subtext,
        "chart_path": chart_path,
        "stat_type": "h2h",
        "raw": h2h,
        "tournament_context": tourn_ctx,
    }


def get_season_leaders_card(stat_type: str = "aces", tournament_name: str = None) -> dict:
    """
    Gera card com ranking de líderes de uma stat na temporada.
    """
    surface = _detect_surface(tournament_name)
    leaders = get_atp_stat_leaders(stat_type, surface=surface, top_n=8)

    if not leaders:
        return {
            "headline": "Líderes da temporada",
            "subtext": "Dados indisponíveis no momento.",
            "chart_path": None,
            "stat_type": "leaders",
            "raw": [],
        }

    label = leaders[0].get("stat", stat_type)
    labels = [l["player"].split()[-1] for l in leaders]
    values = []
    for l in leaders:
        raw_val = l["value"].replace("%", "").replace(",", ".")
        try:
            values.append(float(raw_val))
        except ValueError:
            values.append(0.0)

    chart_path = generate_bar_chart(label, labels, values)
    top_player = leaders[0]["player"]
    top_val    = leaders[0]["value"]

    return {
        "headline": f"{top_player.split()[-1].upper()}: {top_val} {label}",
        "subtext":  f"Líderes de {label} no saibro — dados ATP 2025.",
        "chart_path": chart_path,
        "stat_type": "leaders",
        "raw": leaders,
    }


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _detect_surface(tournament_name: str | None) -> str | None:
    if not tournament_name:
        return None
    t = tournament_name.lower()
    if any(k in t for k in ["rome", "roma", "roland", "garros", "paris", "monte", "madrid", "hamburg", "barcelona"]):
        return "clay"
    if any(k in t for k in ["wimbledon", "queens", "halle", "eastbourne"]):
        return "grass"
    if any(k in t for k in ["us open", "australian", "miami", "indian wells", "toronto", "cincinnati"]):
        return "hard"
    return None


def _serve_headline(srv: dict) -> str:
    player = srv["player"].split()[-1].upper()
    return f"{player}: {srv['first_serve_pct']} 1º saque • {srv['bp_save_pct']} BPs salvos"


def _build_serve_chart(player_name: str, srv: dict) -> str | None:
    try:
        short = player_name.split()[-1]
        labels = ["1º Saque", "Pts no 1º", "Pts no 2º", "BPs Salvos"]
        values = [
            float(srv["first_serve_pct"].replace("%", "")),
            float(srv["first_serve_won_pct"].replace("%", "")),
            float(srv["second_serve_won_pct"].replace("%", "")),
            float(srv["bp_save_pct"].replace("%", "")),
        ]
        return generate_bar_chart(f"SAQUE — {short.upper()}", labels, values)
    except Exception as e:
        log.debug(f"_build_serve_chart falhou: {e}")
        return None


def _build_surface_chart(player_name: str, rec: dict) -> str | None:
    try:
        short = player_name.split()[-1]
        surfaces = [("Clay", rec["clay"]), ("Hard", rec["hard"]), ("Grass", rec["grass"])]
        labels = [s for s, d in surfaces if d["total"] > 0]
        values = [
            round(d["wins"] / d["total"] * 100)
            for _, d in surfaces if d["total"] > 0
        ]
        if not labels:
            return None
        return generate_bar_chart(f"WIN% POR PISO — {short.upper()}", labels, values)
    except Exception as e:
        log.debug(f"_build_surface_chart falhou: {e}")
        return None


def _build_h2h_chart(h2h: dict) -> str | None:
    try:
        a_short = h2h["player_a"].split()[-1]
        b_short = h2h["player_b"].split()[-1]
        surfaces = []
        vals_a, vals_b = [], []
        for surf in ["clay", "hard", "grass"]:
            wa = h2h.get(f"{surf}_a", 0)
            wb = h2h.get(f"{surf}_b", 0)
            if wa + wb > 0:
                surfaces.append(surf.capitalize())
                vals_a.append(wa)
                vals_b.append(wb)

        if not surfaces:
            # Total geral
            labels = [a_short, b_short]
            values = [h2h["wins_a"], h2h["wins_b"]]
        else:
            # Vitórias por superfície do jogador A
            labels = surfaces
            values = vals_a

        return generate_bar_chart(
            f"H2H: {a_short.upper()} vs {b_short.upper()}",
            labels, values
        )
    except Exception as e:
        log.debug(f"_build_h2h_chart falhou: {e}")
        return None
