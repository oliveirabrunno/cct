"""
Wikipedia REST API — foto de perfil do jogador.
Gratuito, sem API key, sempre retorna a foto principal do artigo.
Boa para headshots, não serve para fotos de ação em torneio.
"""

import re
import requests
from utils.logger import get_logger

log = get_logger(__name__)

HEADERS = {
    "User-Agent": "CafeComTenis/1.0 (https://instagram.com/cafecomteniss; cafecomtenis@gmail.com)"
}

# Mapeamento de nome → título exato do artigo na Wikipedia EN
# (evita buscar jogador errado com nome ambíguo)
PLAYER_WIKIPEDIA = {
    # ATP
    "Jannik Sinner":         "Jannik_Sinner",
    "Alexander Zverev":      "Alexander_Zverev",
    "Novak Djokovic":        "Novak_Djokovic",
    "Casper Ruud":           "Casper_Ruud",
    "Carlos Alcaraz":        "Carlos_Alcaraz",
    "Daniil Medvedev":       "Daniil_Medvedev",
    "Holger Rune":           "Holger_Rune",
    "Stefanos Tsitsipas":    "Stefanos_Tsitsipas",
    "João Fonseca":          "João_Fonseca_(tennis)",
    "Felix Auger-Aliassime": "Félix_Auger-Aliassime",
    "Félix Auger-Aliassime": "Félix_Auger-Aliassime",
    "Ben Shelton":           "Ben_Shelton",
    "Taylor Fritz":          "Taylor_Fritz",
    "Alex de Minaur":        "Alex_de_Minaur",
    "Tommy Paul":            "Tommy_Paul_(tennis)",
    "Frances Tiafoe":        "Frances_Tiafoe",
    "Lorenzo Musetti":       "Lorenzo_Musetti",
    "Grigor Dimitrov":       "Grigor_Dimitrov",
    "Andrey Rublev":         "Andrey_Rublev_(tennis)",
    "Hubert Hurkacz":        "Hubert_Hurkacz",
    "Sebastian Korda":       "Sebastian_Korda",
    "Jack Draper":           "Jack_Draper",
    "Alexei Popyrin":        "Alexei_Popyrin",
    "Nuno Borges":           "Nuno_Borges",
    # WTA
    "Aryna Sabalenka":       "Aryna_Sabalenka",
    "Elena Rybakina":        "Elena_Rybakina",
    "Iga Swiatek":           "Iga_Świątek",
    "Iga Świątek":           "Iga_Świątek",
    "Coco Gauff":            "Coco_Gauff",
    "Jessica Pegula":        "Jessica_Pegula",
    "Mirra Andreeva":        "Mirra_Andreeva",
    "Beatriz Haddad Maia":   "Beatriz_Haddad_Maia",
    "Bia Haddad Maia":       "Beatriz_Haddad_Maia",
    "Bia Haddad":            "Beatriz_Haddad_Maia",
    "Madison Keys":          "Madison_Keys",
    "Jasmine Paolini":       "Jasmine_Paolini",
    "Karolína Muchová":      "Karolína_Muchová",
    "Emma Navarro":          "Emma_Navarro",
    "Paula Badosa":          "Paula_Badosa",
    "Daria Kasatkina":       "Daria_Kasatkina",
    "Liudmila Samsonova":    "Liudmila_Samsonova",
    "Qinwen Zheng":          "Zheng_Qinwen",
    "Zheng Qinwen":          "Zheng_Qinwen",
    "Barbora Krejčíková":    "Barbora_Krejčíková",
}


def _slug(name: str) -> str:
    return name.replace(" ", "_")


def get_profile_photo(player_name: str) -> dict | None:
    """
    Retorna a foto principal do artigo do jogador na Wikipedia.
    Geralmente é o headshot mais recente disponível livre.
    """
    title = PLAYER_WIKIPEDIA.get(player_name) or _slug(player_name)
    url   = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 404:
            log.debug(f"Wikipedia: artigo não encontrado para '{player_name}' (título: {title})")
            return None
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.warning(f"Wikipedia summary falhou para '{player_name}': {e}")
        return None

    thumb = data.get("thumbnail") or data.get("originalimage")
    if not thumb:
        log.debug(f"Wikipedia: sem imagem para '{player_name}'")
        return None

    img_url = thumb.get("source", "")
    if not img_url:
        return None

    # Tentar pegar versão maior (960px) via Wikimedia Commons se URL for de lá
    img_url_big = re.sub(r"/\d+px-", "/960px-", img_url)

    log.info(f"Wikipedia profile: '{player_name}' → {img_url_big.split('/')[-1][:50]}")
    return {
        "url":     img_url_big,
        "width":   thumb.get("width", 0),
        "height":  thumb.get("height", 0),
        "license": "CC (Wikipedia)",
        "author":  "Wikipedia",
        "source":  "wikipedia",
    }
