"""
Obtém foto mais recente do Instagram público de um atleta via Playwright.
Crédito obrigatório na legenda: "📸 @{handle}"
"""

from utils.logger import get_logger

log = get_logger(__name__)

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
    "joão fonseca": "joaofonseca__",
    "lorenzo musetti": "lorenzomusetti7",
    "bia haddad": "biahaddadmaia",
    "beatriz haddad maia": "biahaddadmaia",
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
    handle = PLAYER_INSTAGRAM_HANDLES.get(player_name.lower())
    if not handle:
        log.debug(f"Instagram: handle não mapeado para '{player_name}'")
        return None

    log.info(f"Instagram: tentando scraping de @{handle} para '{player_name}'")

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page(
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                           "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
            )

            url = f"https://www.instagram.com/{handle}/"
            await page.goto(url, timeout=20000, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

            # Pegar primeira imagem do grid (não-reel)
            img_el = await page.query_selector("article img")
            if not img_el:
                await browser.close()
                return None

            src = await img_el.get_attribute("src")
            await browser.close()

            if not src:
                return None

            return {
                "url": src,
                "handle": handle,
                "source": "instagram",
                "license": "editorial",
            }

    except Exception as e:
        log.error(f"Instagram scraping falhou para @{handle}: {e}")
        return None
