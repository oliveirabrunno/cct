"""
Scores ao vivo de tênis via Flashscore (Playwright).
Detecta resultados de partidas e dispara geração de breaking news.

FILTRO DE FRESCOR: só retorna partidas das últimas MAX_MATCH_AGE_HOURS horas.
Isso evita que jogos históricos de 2025 ou anteriores sejam postados como breaking news.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from utils.logger import get_logger

log = get_logger(__name__)

# Partidas mais velhas que este limite são ignoradas pelo monitor ao vivo
MAX_MATCH_AGE_HOURS = 48

FLASHSCORE_TENNIS_URL = "https://www.flashscore.com/tennis/"

MONITORED_PLAYERS_LOWER = {
    "sinner", "alcaraz", "djokovic", "zverev", "medvedev",
    "fonseca", "haddad", "swiatek", "sabalenka", "gauff",
    "rublev", "ruud", "fritz", "shelton", "rybakina",
}


async def fetch_live_scores() -> list[dict]:
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            await page.goto(FLASHSCORE_TENNIS_URL, timeout=30000, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

            matches = await page.evaluate("""() => {
                const rows = document.querySelectorAll('[class*="event__match"]');
                const results = [];
                rows.forEach(row => {
                    const home = row.querySelector('[class*="event__participant--home"]');
                    const away = row.querySelector('[class*="event__participant--away"]');
                    const scoreHome = row.querySelector('[class*="event__score--home"]');
                    const scoreAway = row.querySelector('[class*="event__score--away"]');
                    const status = row.querySelector('[class*="event__stage"]');
                    const tournament = document.querySelector('[class*="event__title"]');

                    // Extrair data/hora do jogo a partir de atributos data-* ou texto
                    // O Flashscore usa timestamps Unix no atributo data-start-time
                    const startTs = row.getAttribute('data-start-time')
                        || row.querySelector('[data-start-time]')?.getAttribute('data-start-time')
                        || null;

                    // Tentar pegar a data exibida no bloco de evento (header de data)
                    // Subir no DOM até encontrar o bloco de data do torneio
                    let dateText = '';
                    let el = row.previousElementSibling;
                    for (let i = 0; i < 20 && el; i++) {
                        if (el.className && el.className.includes('event__header')) {
                            dateText = el.textContent.trim();
                            break;
                        }
                        el = el.previousElementSibling;
                    }

                    if (home && away) {
                        results.push({
                            player_a: home.textContent.trim(),
                            player_b: away.textContent.trim(),
                            score_a: scoreHome ? scoreHome.textContent.trim() : '',
                            score_b: scoreAway ? scoreAway.textContent.trim() : '',
                            status: status ? status.textContent.trim() : '',
                            tournament: tournament ? tournament.textContent.trim() : '',
                            start_ts: startTs,     // timestamp Unix (segundos) ou null
                            date_text: dateText,   // texto de data exibido (fallback)
                        });
                    }
                });
                return results;
            }""")

            await browser.close()
            log.info(f"Flashscore: {len(matches)} partidas encontradas")
            return matches

    except Exception as e:
        log.error(f"Flashscore scraping falhou: {e}")
        return []


def _resolve_full_name(abbreviated: str) -> str:
    """
    Converte nome abreviado do Flashscore (ex: 'Darderi L.') para nome completo 
    (ex: 'Luciano Darderi') usando os dados de ranking ao vivo.
    Se não encontrar, tenta inverter 'Sobrenome I.' → 'I. Sobrenome' como fallback.
    """
    if not abbreviated or len(abbreviated) < 3:
        return abbreviated

    try:
        from scrapers.live_ranking import fetch_atp_live_rankings, fetch_wta_live_rankings
        
        # Extrair sobrenome e inicial do formato "Sobrenome I."
        parts = abbreviated.strip().split()
        if len(parts) < 2:
            return abbreviated
        
        surname = parts[0].rstrip(",").lower()
        
        for fetch_fn in [fetch_atp_live_rankings, fetch_wta_live_rankings]:
            try:
                players = fetch_fn(200)
                for p in players:
                    full_name = p.get("name", "")
                    if surname in full_name.lower():
                        return full_name
            except Exception:
                continue
    except Exception:
        pass
    
    # Fallback: inverter "Sobrenome I." → "I. Sobrenome" (melhor que nada)
    parts = abbreviated.strip().split()
    if len(parts) >= 2:
        return f"{' '.join(parts[1:])} {parts[0]}".replace(".", "").strip()
    
    return abbreviated


def _is_match_fresh(m: dict, max_hours: int = MAX_MATCH_AGE_HOURS) -> bool:
    """
    Verifica se a partida aconteceu dentro do limite de horas.

    Fontes de data (em ordem de prioridade):
      1. start_ts — timestamp Unix capturado do atributo data-start-time do Flashscore
      2. date_text — texto de data exibido no cabeçalho do evento (heurística)
      3. Sem data disponível — assume FRESCO (não descarta por precaução)
    """
    now = datetime.now(tz=timezone.utc)
    cutoff = now - timedelta(hours=max_hours)

    # 1. Timestamp Unix
    start_ts = m.get("start_ts")
    if start_ts:
        try:
            match_dt = datetime.fromtimestamp(int(start_ts), tz=timezone.utc)
            fresh = match_dt >= cutoff
            if not fresh:
                log.debug(f"Ignorando partida antiga ({match_dt.date()}): {m.get('player_a')} vs {m.get('player_b')}")
            return fresh
        except (ValueError, TypeError):
            pass

    # 2. Texto de data (heurística: se contém ano diferente do atual, é velho)
    date_text = m.get("date_text", "")
    current_year = str(now.year)
    if date_text:
        # Se o texto menciona explicitamente um ano que não é o atual
        import re
        years_found = re.findall(r"\b(20\d{2})\b", date_text)
        for y in years_found:
            if y != current_year:
                log.debug(f"Ignorando partida de {y}: {m.get('player_a')} vs {m.get('player_b')}")
                return False

    # 3. Sem informação de data — assume fresco (melhor false negative que false positive)
    log.debug(f"Sem timestamp para '{m.get('player_a')} vs {m.get('player_b')}' — assumindo fresco")
    return True


async def check_completed_matches(max_age_hours: int = MAX_MATCH_AGE_HOURS) -> list[dict]:
    """Retorna apenas partidas finalizadas nas últimas max_age_hours horas envolvendo atletas monitorados."""
    all_matches = await fetch_live_scores()
    completed = []
    seen_matches: set[str] = set()  # Dedup interno: evitar retornar o mesmo jogo 2x

    for m in all_matches:
        status = m.get("status", "").lower()
        is_finished = any(s in status for s in ["finished", "fim", "final", "retired", "walkover"])
        if not is_finished:
            continue

        # ✅ Filtro de frescor: ignorar partidas mais antigas que max_age_hours
        if not _is_match_fresh(m, max_hours=max_age_hours):
            log.info(f"Partida descartada (muito antiga): {m.get('player_a')} vs {m.get('player_b')}")
            continue

        player_a = m.get("player_a", "").lower()
        player_b = m.get("player_b", "").lower()

        # Dedup interno: mesmo par de jogadores = mesmo jogo
        pair_key = "_".join(sorted([player_a, player_b]))
        if pair_key in seen_matches:
            log.debug(f"Partida duplicada no Flashscore (mesmo par), ignorando: {player_a} vs {player_b}")
            continue
        seen_matches.add(pair_key)

        is_monitored = any(
            p in player_a or p in player_b
            for p in MONITORED_PLAYERS_LOWER
        )
        if not is_monitored:
            continue

        # Determinar vencedor pelo score
        score_a = m.get("score_a", "")
        score_b = m.get("score_b", "")
        
        # Resolver nomes abreviados para nomes completos
        winner_raw = m["player_a"] if score_a > score_b else m["player_b"]
        loser_raw  = m["player_b"] if score_a > score_b else m["player_a"]
        
        winner_full = _resolve_full_name(winner_raw)
        loser_full  = _resolve_full_name(loser_raw)
        
        log.info(f"Nomes resolvidos: {winner_raw} → {winner_full} | {loser_raw} → {loser_full}")

        completed.append({
            "player_a": m["player_a"],
            "player_b": m["player_b"],
            "score": f"{score_a}-{score_b}",
            "winner": winner_full,
            "loser":  loser_full,
            "tournament": m.get("tournament", ""),
            "timestamp": datetime.now().isoformat(),
        })

    log.info(f"Partidas finalizadas (monitoradas): {len(completed)}")
    return completed


async def get_recent_tournament_winner(tour: str = "ATP") -> str | None:
    """
    Busca o vencedor do torneio mais recente (final concluída) para ATP ou WTA.
    Usa Playwright para pegar o último resultado de final em flashscore.com.
    Retorna nome completo do vencedor ou None se não encontrar.
    """
    try:
        from playwright.async_api import async_playwright

        tour_lower = tour.lower()
        url = f"https://www.flashscore.com/tennis/{tour_lower}/"

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            await page.goto(url, timeout=30000, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

            # Procurar partidas marcadas como "Final" já finalizadas
            result = await page.evaluate("""() => {
                const rows = document.querySelectorAll("[class*='event__match']");
                for (const row of rows) {
                    const status = row.querySelector("[class*='event__stage']");
                    const round  = row.querySelector("[class*='event__round']");
                    if (!status) continue;
                    const st = status.textContent.trim().toLowerCase();
                    const rd = round ? round.textContent.trim().toLowerCase() : '';
                    const finished = ['finished','fim','fin','ended','final'].some(s => st.includes(s));
                    const isFinal = rd.includes('final') || rd.includes('f ');
                    if (finished && isFinal) {
                        const home  = row.querySelector("[class*='event__participant--home']");
                        const away  = row.querySelector("[class*='event__participant--away']");
                        const scoreH = row.querySelector("[class*='event__score--home']");
                        const scoreA = row.querySelector("[class*='event__score--away']");
                        if (!home || !away) continue;
                        const sH = parseInt(scoreH ? scoreH.textContent.trim() : '0');
                        const sA = parseInt(scoreA ? scoreA.textContent.trim() : '0');
                        return sH > sA ? home.textContent.trim() : away.textContent.trim();
                    }
                }
                return null;
            }""")
            await browser.close()

        if result:
            winner_full = _resolve_full_name(result)
            log.info(f"Vencedor recente ({tour}): {result} → {winner_full}")
            return winner_full

    except Exception as e:
        log.debug(f"get_recent_tournament_winner falhou ({tour}): {e}")

    return None
