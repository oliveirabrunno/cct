"""
Gera Reels: slides PNG + áudio TTS → MP4 com FFmpeg.
Formato: 1080x1920 (9:16 vertical), 30fps.
Cada slide tem duração baseada no texto narrado.
"""

import asyncio
import json
import os
import subprocess
import time
import tempfile
from pathlib import Path
from PIL import Image

from generators.tts import generate_tts
from generators.story import StoryGenerator
from generators.content import ContentGenerator
from utils.image_manager import ImageManager
from utils.image_processor import ImageProcessor
from utils.logger import get_logger

log = get_logger(__name__)

OUTPUT_DIR = Path("output/queue")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

REEL_W = 1080
REEL_H = 1920
FPS    = 30

# Segundos por palavra (estimativa para narração em pt-BR)
WORDS_PER_SECOND = 2.8


def _estimate_duration(text: str) -> float:
    words = len(text.split())
    return max(3.0, words / WORDS_PER_SECOND)


def _pad_image_to_reel(img_path: str, output_path: str) -> str:
    """Converte qualquer imagem para 1080x1920 com letterbox/pillarbox escuro."""
    img = Image.open(img_path).convert("RGB")
    canvas = Image.new("RGB", (REEL_W, REEL_H), (10, 10, 10))

    # Escalar mantendo proporção
    scale = min(REEL_W / img.width, REEL_H / img.height)
    new_w = int(img.width * scale)
    new_h = int(img.height * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    # Centralizar
    x = (REEL_W - new_w) // 2
    y = (REEL_H - new_h) // 2
    canvas.paste(img, (x, y))
    canvas.save(output_path, "JPEG", quality=95)
    return output_path


def _escape_ffmpeg_text(text: str) -> str:
    """Escapa caracteres especiais para o filtro drawtext do FFmpeg."""
    # Ordem importa: \ primeiro, depois os outros
    text = text.replace("\\", "\\\\")
    text = text.replace("'",  "’")   # apóstrofo tipográfico — evita quebrar o filtro
    text = text.replace(":",  "\\:")
    text = text.replace("[",  "\\[").replace("]", "\\]")
    return text


def _wrap_text(text: str, max_chars: int = 32) -> str:
    """Quebra texto longo em múltiplas linhas para o drawtext."""
    words = text.split()
    lines, current = [], ""
    for word in words:
        if len(current) + len(word) + 1 <= max_chars:
            current = f"{current} {word}".strip()
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return "\n".join(lines)


def _build_subtitle_filter(text: str, video_width: int = REEL_W, video_height: int = REEL_H) -> str:
    """
    Retorna o filtro FFmpeg drawtext para legenda burn-in.
    Estilo: caixa escura semitransparente, texto branco centralizado,
    posicionado na zona segura inferior do reel (acima dos botões do Instagram).
    """
    if not text:
        return ""

    # Fonte disponível em macOS e Linux (via fontconfig)
    font_candidates = [
        "/System/Library/Fonts/Helvetica.ttc",           # macOS
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Ubuntu/Debian
        "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",  # CentOS/RHEL
    ]
    font_path = next((f for f in font_candidates if Path(f).exists()), "")

    escaped = _escape_ffmpeg_text(_wrap_text(text, max_chars=28))

    # y = h*0.78 coloca a legenda na zona segura (abaixo da imagem mas acima dos botões)
    font_param = f":fontfile='{font_path}'" if font_path else ""
    return (
        f"drawtext=text='{escaped}'"
        f"{font_param}"
        f":fontsize=58"
        f":fontcolor=white"
        f":font=Helvetica"
        f":x=(w-text_w)/2"
        f":y=h*0.78-text_h/2"
        f":box=1"
        f":boxcolor=black@0.65"
        f":boxborderw=24"
        f":line_spacing=8"
    )


async def generate_reel_from_carousel(
    slides: list[dict],
    slide_images: list[str],
    player_name: str,
    post_type: str = "trend",
    voice: str | None = None,
    burn_subtitles: bool = True,
) -> str | None:
    """
    Gera um Reel a partir de slides de carrossel existentes.

    slides:          lista de dicts com 'headline' e 'subtext'
    slide_images:    paths dos PNGs gerados
    burn_subtitles:  queima legenda do headline em cada slide (padrão: True)
    Retorna:         path do MP4 gerado
    """
    if not slide_images:
        log.error("Nenhuma imagem de slide fornecida")
        return None

    tmp_dir = Path(tempfile.mkdtemp(prefix="reel_"))
    log.info(f"Gerando reel em {tmp_dir}")

    try:
        segments = []

        for i, (slide, img_path) in enumerate(zip(slides, slide_images)):
            headline = slide.get("headline", "")
            subtext  = slide.get("subtext", "")
            narration = f"{headline}. {subtext}".strip(". ")

            if not narration:
                narration = headline or subtext or f"Slide {i+1}"

            # Gerar áudio do slide
            audio_path = str(tmp_dir / f"audio_{i:02d}.mp3")
            audio = await generate_tts(narration, audio_path, voice)

            # Duração: usa tamanho real do áudio se disponível
            duration = _estimate_duration(narration)
            if audio and Path(audio).exists():
                duration = await _get_audio_duration(audio)
                duration = max(duration + 0.3, 3.0)  # padding

            # Converter slide para formato reel
            reel_img = str(tmp_dir / f"slide_{i:02d}.jpg")
            _pad_image_to_reel(img_path, reel_img)

            segments.append({
                "image":    reel_img,
                "audio":    audio,
                "duration": duration,
                "subtitle": headline if burn_subtitles else "",
                "slide_index": i,
            })

        # Montar o MP4
        output_path = str(OUTPUT_DIR / f"reel_{post_type}_{int(time.time())}.mp4")
        success = await _assemble_mp4(segments, output_path)

        if success:
            log.info(f"Reel gerado: {output_path}")
            return output_path
        return None

    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


async def generate_quick_reel(
    player_name: str,
    headline: str,
    body: str,
    bg_image: str | None = None,
    duration: float = 15.0,
) -> str | None:
    """
    Reel rápido (1 slide + narração) para breaking news.
    Ideal para postar em até 8 minutos após um resultado.
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="quickreel_"))

    try:
        # Gerar áudio
        narration = f"{headline}. {body}"
        audio_path = str(tmp_dir / "audio.mp3")
        audio = await generate_tts(narration, audio_path)
        actual_duration = await _get_audio_duration(audio) + 1.0 if audio else duration

        # Imagem de fundo
        if bg_image and Path(bg_image).exists():
            reel_img = str(tmp_dir / "bg.jpg")
            _pad_image_to_reel(bg_image, reel_img)
        else:
            # Gerar slide breaking news via StoryGenerator
            gen = StoryGenerator()
            story = await gen.generate_breaking_story({
                "winner": player_name,
                "loser": "",
                "score": "",
                "tournament": "",
                "top_stat": headline,
            })
            reel_img = story if story else None

        if not reel_img:
            log.error("Sem imagem para o reel")
            return None

        segments = [{"image": reel_img, "audio": audio, "duration": actual_duration, "subtitle": headline}]
        output_path = str(OUTPUT_DIR / f"reel_quick_{int(time.time())}.mp4")
        success = await _assemble_mp4(segments, output_path)
        return output_path if success else None

    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


async def _get_audio_duration(audio_path: str) -> float:
    """Retorna duração do áudio em segundos via ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_streams", audio_path],
            capture_output=True, text=True, timeout=10
        )
        data = json.loads(result.stdout)
        duration = float(data["streams"][0].get("duration", 5.0))
        return duration
    except Exception:
        return 5.0


async def _assemble_mp4(segments: list[dict], output_path: str) -> bool:
    """
    Monta o MP4 final com FFmpeg.
    Cada segmento: imagem estática + áudio opcional.
    Usa concat demuxer para unir todos os segmentos.
    """
    tmp_dir = Path(output_path).parent / f"_concat_{int(time.time())}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    try:
        segment_files = []

        for i, seg in enumerate(segments):
            seg_output = str(tmp_dir / f"seg_{i:02d}.mp4")
            img      = seg["image"]
            audio    = seg.get("audio")
            dur      = seg["duration"]
            subtitle = seg.get("subtitle", "")

            # Construir filtro de vídeo: scale + pad + legenda opcional
            scale_pad = (
                f"scale={REEL_W}:{REEL_H}:force_original_aspect_ratio=decrease,"
                f"pad={REEL_W}:{REEL_H}:(ow-iw)/2:(oh-ih)/2:color=0x0A0A0A"
            )
            sub_filter = _build_subtitle_filter(subtitle) if subtitle else ""
            vf = f"{scale_pad},{sub_filter}" if sub_filter else scale_pad

            if audio and Path(audio).exists():
                cmd = [
                    "ffmpeg", "-y",
                    "-loop", "1", "-i", img,
                    "-i", audio,
                    "-c:v", "libx264", "-tune", "stillimage",
                    "-c:a", "aac", "-b:a", "192k",
                    "-pix_fmt", "yuv420p",
                    "-t", str(dur),
                    "-vf", vf,
                    "-r", str(FPS),
                    "-shortest",
                    seg_output
                ]
            else:
                cmd = [
                    "ffmpeg", "-y",
                    "-loop", "1", "-i", img,
                    "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                    "-c:v", "libx264", "-tune", "stillimage",
                    "-c:a", "aac", "-b:a", "192k",
                    "-pix_fmt", "yuv420p",
                    "-t", str(dur),
                    "-vf", vf,
                    "-r", str(FPS),
                    seg_output
                ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                log.error(f"FFmpeg segmento {i} falhou: {result.stderr[-300:]}")
                return False

            segment_files.append(seg_output)

        # Concat
        if len(segment_files) == 1:
            import shutil
            shutil.copy(segment_files[0], output_path)
            return True

        concat_list = tmp_dir / "concat.txt"
        with open(concat_list, "w") as f:
            for sf in segment_files:
                abs_path = str(Path(sf).resolve())
                f.write(f"file '{abs_path}'\n")

        concat_cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            output_path
        ]
        result = subprocess.run(concat_cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            log.error(f"FFmpeg concat falhou: {result.stderr[-300:]}")
            return False

        size_mb = Path(output_path).stat().st_size / (1024 * 1024)
        log.info(f"MP4 finalizado: {output_path} ({size_mb:.1f} MB)")
        return True

    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)
