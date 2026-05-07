"""
TTS em cascata: ElevenLabs → edge-tts (Microsoft pt-BR) → gTTS (Google).

Vozes ElevenLabs disponíveis na conta:
  Paulo (conteúdo) : Qrdut83w0Cr152Yb4Xn3   ← padrão reels
  Brunno (clone)   : xHhrvzP1LUfmNLUKwja3   ← voz própria do criador
  Brunno Scale     : J7LJHsXx0SvZ7CAV6npY   ← otimizada para volume

Fallback edge-tts (Microsoft, gratuito, sem quota):
  pt-BR-AntonioNeural  — masculino, natural
  pt-BR-FranciscaNeural — feminino, alternativa
"""

import asyncio
import os
import time
from pathlib import Path
from utils.logger import get_logger

log = get_logger(__name__)

# ─── Configuração ─────────────────────────────────────────────────────────────

ELEVENLABS_KEY   = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE = os.getenv("ELEVENLABS_VOICE_ID", "Qrdut83w0Cr152Yb4Xn3")  # Paulo padrão

EDGE_VOICE_PRIMARY = os.getenv("EDGE_VOICE", "pt-BR-AntonioNeural")
EDGE_VOICE_ALT     = "pt-BR-FranciscaNeural"

# Cache de estado da quota — evita tentativas desnecessárias durante a sessão
_elevenlabs_quota_ok: bool | None = None


# ─── Ponto de entrada principal ───────────────────────────────────────────────

async def generate_tts(
    text: str,
    output_path: str | None = None,
    voice: str | None = None,
    force_edge: bool = False,
) -> str | None:
    """
    Gera áudio do texto com fallback automático.

    force_edge=True: pula ElevenLabs e usa edge-tts diretamente (mais rápido).
    """
    global _elevenlabs_quota_ok

    if not output_path:
        output_path = f"/tmp/tts_{int(time.time())}.mp3"

    # 1. ElevenLabs — melhor qualidade, só tenta se quota estiver ok
    if not force_edge and ELEVENLABS_KEY and _elevenlabs_quota_ok is not False:
        result = await _elevenlabs_tts(text, output_path)
        if result:
            _elevenlabs_quota_ok = True
            return result

    # 2. edge-tts (Microsoft, gratuito, excelente pt-BR, sem quota)
    edge_voice = voice if voice and "Neural" in voice else EDGE_VOICE_PRIMARY
    result = await _edge_tts(text, output_path, edge_voice)
    if result:
        return result

    # 3. gTTS (último fallback, não precisa de instalação adicional)
    return _gtts_fallback(text, output_path)


# ─── Provedores ───────────────────────────────────────────────────────────────

async def _elevenlabs_tts(text: str, output_path: str, voice_id: str | None = None) -> str | None:
    global _elevenlabs_quota_ok
    import requests

    vid = voice_id or ELEVENLABS_VOICE
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{vid}"

    try:
        resp = requests.post(
            url,
            headers={
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": ELEVENLABS_KEY,
            },
            json={
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {"stability": 0.50, "similarity_boost": 0.75, "style": 0.2},
            },
            timeout=30,
        )

        if resp.status_code == 401:
            detail = resp.json().get("detail", {})
            if isinstance(detail, dict) and detail.get("status") == "quota_exceeded":
                log.warning("ElevenLabs: quota esgotada — fallback para edge-tts até próximo ciclo")
                _elevenlabs_quota_ok = False  # não tenta mais nesta sessão
            else:
                log.warning(f"ElevenLabs: auth falhou ({detail}) — fallback para edge-tts")
            return None

        resp.raise_for_status()
        Path(output_path).write_bytes(resp.content)
        log.info(f"TTS ElevenLabs (voice:{vid}): {output_path}")
        return output_path

    except Exception as e:
        log.warning(f"ElevenLabs erro: {e} — fallback para edge-tts")
        return None


async def _edge_tts(text: str, output_path: str, voice: str) -> str | None:
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)
        log.info(f"TTS edge-tts [{voice}]: {output_path}")
        return output_path
    except Exception as e:
        log.warning(f"edge-tts [{voice}] falhou: {e}")
        # Tentar voz alternativa
        if voice != EDGE_VOICE_ALT:
            return await _edge_tts(text, output_path, EDGE_VOICE_ALT)
        return None


def _gtts_fallback(text: str, output_path: str) -> str | None:
    try:
        from gtts import gTTS
        gTTS(text=text, lang="pt", slow=False).save(output_path)
        log.info(f"TTS gTTS: {output_path}")
        return output_path
    except Exception as e:
        log.error(f"gTTS falhou: {e}")
        return None


# ─── Utilitários ──────────────────────────────────────────────────────────────

async def check_elevenlabs_quota() -> dict:
    """Verifica quota disponível e retorna status."""
    import requests
    try:
        resp = requests.get(
            "https://api.elevenlabs.io/v1/user/subscription",
            headers={"xi-api-key": ELEVENLABS_KEY},
            timeout=10,
        )
        data = resp.json()
        remaining = data.get("character_limit", 0) - data.get("character_count", 0)
        reset_ts  = data.get("next_character_count_reset_unix", 0)
        from datetime import datetime
        reset_date = datetime.fromtimestamp(reset_ts).strftime("%d/%m/%Y") if reset_ts else "?"
        status = {
            "remaining": remaining,
            "limit": data.get("character_limit", 0),
            "reset_date": reset_date,
            "ok": remaining > 100,
        }
        log.info(f"ElevenLabs quota: {remaining} créditos restantes (reset: {reset_date})")
        return status
    except Exception as e:
        log.error(f"Erro ao verificar quota ElevenLabs: {e}")
        return {"remaining": 0, "ok": False}


async def sample_voices(text: str = "Sinner já tem mais pontos que Federer no pico da carreira."):
    """Gera amostras de todas as vozes disponíveis para comparação."""
    voices = {
        "edge_antonio":   (None, "pt-BR-AntonioNeural"),
        "edge_francisca": (None, "pt-BR-FranciscaNeural"),
        "el_paulo":       ("Qrdut83w0Cr152Yb4Xn3", None),
        "el_brunno":      ("xHhrvzP1LUfmNLUKwja3", None),
        "el_brunno_scale":("J7LJHsXx0SvZ7CAV6npY", None),
    }

    print("Gerando amostras de voz...\n")
    for label, (el_voice, edge_voice) in voices.items():
        path = f"/tmp/sample_{label}.mp3"
        if el_voice:
            result = await _elevenlabs_tts(text, path, el_voice)
        else:
            result = await _edge_tts(text, path, edge_voice)
        status = "✅" if result else "❌"
        print(f"{status} {label}: {path}")
