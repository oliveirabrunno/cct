"""
Scores ao vivo de tênis via Flashscore (Playwright).
Detecta resultados de partidas e dispara geração de breaking news.
"""

import asyncio
from datetime import datetime
from utils.logger import get_logger

log = get_logger(__name__)

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

                    if (home && away) {
                        results.push({
                            player_a: home.textContent.trim(),
                            player_b: away.textContent.trim(),
                            score_a: scoreHome ? scoreHome.textContent.trim() : "",
                            score_b: scoreAway ? scoreAway.textContent.trim() : "",
                            status: status ? status.textContent.trim() : "",
                            tournament: tournament ? tournament.textContent.trim() : ""
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


async def check_completed_matches() -> list[dict]:
    """Retorna apenas partidas finalizadas envolvendo atletas monitorados."""
    all_matches = await fetch_live_scores()
    completed = []

    for m in all_matches:
        status = m.get("status", "").lower()
        is_finished = any(s in status for s in ["finished", "fim", "final", "retired", "walkover"])
        if not is_finished:
            continue

        player_a = m.get("player_a", "").lower()
        player_b = m.get("player_b", "").lower()

        is_monitored = any(
            p in player_a or p in player_b
            for p in MONITORED_PLAYERS_LOWER
        )
        if not is_monitored:
            continue

        # Determinar vencedor pelo score
        score_a = m.get("score_a", "")
        score_b = m.get("score_b", "")

        completed.append({
            "player_a": m["player_a"],
            "player_b": m["player_b"],
            "score": f"{score_a}-{score_b}",
            "winner": m["player_a"] if score_a > score_b else m["player_b"],
            "loser":  m["player_b"] if score_a > score_b else m["player_a"],
            "tournament": m.get("tournament", ""),
            "timestamp": datetime.now().isoformat(),
        })

    log.info(f"Partidas finalizadas (monitoradas): {len(completed)}")
    return completed
