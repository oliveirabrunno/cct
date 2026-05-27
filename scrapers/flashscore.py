"""
Scores ao vivo de tênis via Flashscore (Playwright).
Detecta resultados de partidas e dispara geração de breaking news.

FILTROS DE SEGURANÇA:
  - FRESCOR: só retorna partidas das últimas MAX_MATCH_AGE_HOURS horas.
  - SINGLES ONLY: ignora duplas (nomes com '/', torneios com 'doubles').
  - SEM TIMESTAMP: assume VELHO por segurança (melhor perder do que postar lixo).

Incidentes corrigidos:
  - 2026-05-21: duplas "Arneodo def Fritz" e "Gonzalez-Galino def Alcaraz" publicadas
    como se fossem resultados de singles.
"""

import asyncio
import re
from datetime import datetime, timedelta, timezone
from utils.logger import get_logger

log = get_logger(__name__)

# Partidas mais velhas que este limite são ignoradas pelo monitor ao vivo.
# 12h dá folga para Grand Slams onde jogos terminam tarde e o cron pode atrasar.
MAX_MATCH_AGE_HOURS = 12

FLASHSCORE_TENNIS_URL = "https://www.flashscore.com/tennis/"
# Durante Grand Slams, monitorar diretamente a página do torneio para captura mais confiável
FLASHSCORE_RG_URL = "https://www.flashscore.com/tennis/atp-singles/french-open/"
FLASHSCORE_RG_WTA_URL = "https://www.flashscore.com/tennis/wta-singles/french-open/"

MONITORED_PLAYERS_LOWER = {
    "sinner", "alcaraz", "djokovic", "zverev", "medvedev",
    "fonseca", "haddad", "swiatek", "sabalenka", "gauff",
    "rublev", "ruud", "fritz", "shelton", "rybakina",
}


async def fetch_live_scores(urls: list[str] | None = None) -> list[dict]:
    # Por padrão, varrer a página geral + URLs específicas de Grand Slams ativos.
    # Cobertura melhor pra Roland Garros, US Open, Wimbledon, Australian Open.
    if urls is None:
        urls = [FLASHSCORE_TENNIS_URL, FLASHSCORE_RG_URL, FLASHSCORE_RG_WTA_URL]
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            all_matches: list[dict] = []
            for url in urls:
                try:
                    page = await browser.new_page(
                        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    )
                    await page.goto(url, timeout=30000, wait_until="domcontentloaded")
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

                            const startTs = row.getAttribute('data-start-time')
                                || row.querySelector('[data-start-time]')?.getAttribute('data-start-time')
                                || null;

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
                                    start_ts: startTs,
                                    date_text: dateText,
                                });
                            }
                        });
                        return results;
                    }""")
                    all_matches.extend(matches)
                    await page.close()
                except Exception as inner_e:
                    log.warning(f"Flashscore falhou para {url}: {inner_e}")
                    continue

            await browser.close()
            # Dedup por par de jogadores (a mesma partida pode aparecer em múltiplas URLs)
            seen = set()
            unique: list[dict] = []
            for m in all_matches:
                key = "_".join(sorted([m.get("player_a", "").lower(), m.get("player_b", "").lower()]))
                if key in seen:
                    continue
                seen.add(key)
                unique.append(m)
            log.info(f"Flashscore: {len(unique)} partidas únicas em {len(urls)} URLs")
            return unique

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


def _is_doubles_match(m: dict) -> bool:
    """
    Detecta se a partida é de duplas.

    Sinais de dupla:
      - Nome do jogador contém '/' (ex: 'Arneodo / Nys', 'Gonzalez / Galino')
      - Torneio contém 'doubles', 'dobles', 'doppio', 'doppel'
      - Nome contém ',' seguido de espaço e outro nome (formato alternativo)

    Adicionado após incidente de 2026-05-21: duplas publicadas como singles.
    """
    player_a = m.get("player_a", "")
    player_b = m.get("player_b", "")
    tournament = m.get("tournament", "").lower()

    # '/' no nome é o sinal mais forte de dupla
    if "/" in player_a or "/" in player_b:
        log.debug(f"Partida de DUPLAS detectada (nome com '/'): {player_a} vs {player_b}")
        return True

    # Torneio com "doubles" no nome
    doubles_keywords = ["doubles", "dobles", "doppio", "doppel", "duplas"]
    if any(kw in tournament for kw in doubles_keywords):
        log.debug(f"Partida de DUPLAS detectada (torneio): {tournament}")
        return True

    # Padrão alternativo: "Sobrenome A. / Sobrenome B." ou "Name, Name"
    # Múltiplos espaços + pontos sugerem formato de dupla
    for name in [player_a, player_b]:
        # Conta quantos pontos (iniciais) aparecem — duplas têm 2+ iniciais
        initials = re.findall(r'\b[A-Z]\.$', name.strip())
        parts = name.split()
        if len(parts) >= 4:  # dupla: "Sobrenome I. Sobrenome2 I."
            log.debug(f"Partida de DUPLAS suspeita (muitas partes no nome): {name}")
            return True

    return False


def _is_match_fresh(m: dict, max_hours: int = MAX_MATCH_AGE_HOURS) -> bool:
    """
    Verifica se a partida aconteceu dentro do limite de horas.

    Fontes de data (em ordem de prioridade):
      1. start_ts — timestamp Unix capturado do atributo data-start-time do Flashscore
      2. date_text — texto de data exibido no cabeçalho do evento (heurística)
      3. Sem data disponível — assume VELHO (conservador: melhor perder resultado
         do que publicar jogo antigo)

    Mudança de 2026-05-21: default era "fresco" → mudou para "velho".
    Motivo: partidas sem timestamp estavam passando e gerando posts de jogos antigos.
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
        years_found = re.findall(r"\b(20\d{2})\b", date_text)
        for y in years_found:
            if y != current_year:
                log.debug(f"Ignorando partida de {y}: {m.get('player_a')} vs {m.get('player_b')}")
                return False
        # Se o texto de data existe e não contém ano errado, considerar fresco
        return True

    # 3. Sem informação de data — assume VELHO por segurança
    # (melhor perder um resultado do que publicar jogo antigo no feed)
    log.warning(
        f"Sem timestamp para '{m.get('player_a')} vs {m.get('player_b')}' "
        "— descartando por segurança (sem data = possível jogo antigo)"
    )
    return False


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

        # ✅ Filtro de duplas: NUNCA publicar resultados de duplas como singles
        if _is_doubles_match(m):
            log.info(f"Partida de DUPLAS ignorada: {m.get('player_a')} vs {m.get('player_b')}")
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
