"""
Deduplicação de posts — 3 camadas de proteção contra postagens duplicadas/antigas.

Camada 1 — SQLite local (database.sqlite):
  Rápido, funciona offline. Persiste entre runs via GitHub Actions cache.
  PROBLEMA: o cache Actions pode ser restaurado de uma versão antiga → falso negativo.

Camada 2 — Instagram Graph API (últimos N posts):
  Busca os últimos 20 posts do feed real para verificar se o tema já foi postado.
  Funciona mesmo quando o cache local está desatualizado ou vazio.
  Compara keywords do jogador/tema na legenda dos posts.

Camada 3 — Dedup de conteúdo por hash (content_hash):
  Hash SHA-256 do post_type + player + extra. Evita re-post exato.

Freshness guard (em flashscore.py e match_result_card.py):
  Rejeita partidas com mais de 48h, independente do dedup.
"""

import hashlib
import os
import sqlite3
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from utils.logger import get_logger

log = get_logger(__name__)

DB_PATH = Path("data/database.sqlite")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Cache em memória dos posts do Instagram (evita múltiplas chamadas por run)
# Invalidado após cada publicação para garantir que o próximo dedup veja o post recém-publicado
_ig_posts_cache: list[dict] | None = None


def _invalidate_ig_cache() -> None:
    """Limpa o cache de posts do IG para forçar reconsulta na próxima verificação."""
    global _ig_posts_cache
    _ig_posts_cache = None
    log.debug("Cache IG invalidado")


# ── SQLite helpers ────────────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            content_hash TEXT UNIQUE NOT NULL,
            post_type    TEXT,
            player       TEXT,
            description  TEXT,
            published_at TEXT NOT NULL,
            ig_post_id   TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS image_urls (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            url_hash   TEXT UNIQUE NOT NULL,
            url_preview TEXT,
            player     TEXT,
            source     TEXT,
            used_at    TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def _normalize_string(s: str) -> str:
    if not s:
        return ""
    s = s.lower().strip()
    return unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('utf-8')


def content_hash(post_type: str, player: str, extra: str = "") -> str:
    raw = f"{_normalize_string(post_type)}:{_normalize_string(player)}:{_normalize_string(extra)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ── Camada 2: Instagram Graph API ────────────────────────────────────────────

def _fetch_ig_recent_posts(limit: int = 20) -> list[dict]:
    """
    Busca os últimos `limit` posts do feed do Instagram via Graph API.
    Usa graph.facebook.com (necessário para tokens de PAGE — não graph.instagram.com).
    Retorna lista de dicts com caption, timestamp, id.
    """
    global _ig_posts_cache
    if _ig_posts_cache is not None:
        return _ig_posts_cache

    token   = os.environ.get("META_ACCESS_TOKEN", "")
    user_id = os.environ.get("META_IG_USER_ID", "")
    if not token or not user_id:
        log.debug("IG Graph API não configurada — dedup de API desabilitado")
        _ig_posts_cache = []
        return []

    try:
        import requests
        # IMPORTANTE: usar graph.facebook.com, não graph.instagram.com
        # O token de PAGE não é aceito em graph.instagram.com (retorna 400)
        resp = requests.get(
            f"https://graph.facebook.com/v22.0/{user_id}/media",
            params={
                "fields":       "id,caption,timestamp",
                "limit":        limit,
                "access_token": token,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        _ig_posts_cache = data
        log.info(f"IG dedup: {len(data)} posts recentes carregados via Graph API")
        return data
    except Exception as e:
        log.warning(f"IG Graph API falhou para dedup: {e}")
        _ig_posts_cache = []
        return []


def _ig_has_recent_post(player: str, hours: int = 24) -> bool:
    """
    Verifica se o feed do Instagram já tem um post sobre este jogador/tema
    nas últimas `hours` horas.
    Compara keywords do nome do jogador com as legendas.
    """
    posts = _fetch_ig_recent_posts()
    if not posts:
        return False

    # Keywords a buscar: partes do nome do jogador
    keywords = [w.lower() for w in player.split() if len(w) > 3]
    cutoff   = datetime.utcnow() - timedelta(hours=hours)

    for post in posts:
        # Verificar data
        ts_str = post.get("timestamp", "")
        try:
            from datetime import timezone
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            ts = ts.replace(tzinfo=None)  # comparar naive
            if ts < cutoff:
                continue  # post mais antigo que o limite
        except Exception:
            continue

        caption = _normalize_string(post.get("caption", ""))
        if any(kw in caption for kw in keywords):
            log.info(
                f"IG dedup: '{player}' encontrado em post recente "
                f"({post.get('id')}, {ts_str[:10]})"
            )
            return True

    return False


# ── API pública ───────────────────────────────────────────────────────────────

def is_duplicate(
    post_type: str,
    player: str,
    extra: str = "",
    hours: int = 72,
    check_ig: bool = True,
) -> bool:
    """
    Verifica se já existe um post idêntico/similar recente.

    Camada 1: SQLite local (hash exato)
    Camada 2: Instagram Graph API (keywords do jogador nos últimos posts)
    """
    # Camada 1 — SQLite
    h      = content_hash(post_type, player, extra)
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

    with _get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM posts WHERE content_hash = ? AND published_at > ?",
            (h, cutoff)
        ).fetchone()

    if row:
        log.info(f"Duplicado detectado (SQLite): {post_type}/{player} (hash {h})")
        return True

    # Camada 2 — Instagram Graph API
    if check_ig and player and player.lower() not in ("test player", ""):
        # Para match_result: checagem mais curta (24h); demais: igual ao hours
        ig_hours = min(hours, 24) if post_type == "match_result" else min(hours, 48)
        if _ig_has_recent_post(player, hours=ig_hours):
            log.info(f"Duplicado detectado (IG API): {post_type}/{player}")
            return True

    return False


def register_post(
    post_type: str,
    player: str,
    extra: str = "",
    ig_post_id: str = "",
    description: str = "",
) -> None:
    h = content_hash(post_type, player, extra)
    with _get_conn() as conn:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO posts (content_hash, post_type, player, description, published_at, ig_post_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (h, post_type, player, description, datetime.now().isoformat(), ig_post_id)
            )
            conn.commit()
            log.info(f"Post registrado: {post_type}/{player} → {h}")
        except sqlite3.IntegrityError:
            pass
    # Invalidar cache do IG para que a próxima verificação de dedup
    # veja o post recém-publicado (evita duplicatas na mesma run)
    _invalidate_ig_cache()


def register_used_image(player: str, filename: str) -> None:
    """Registra arquivo de imagem como usado (evita repetição por 7 dias)."""
    key = f"{_normalize_string(player)}::{filename}"
    h = hashlib.sha256(key.encode()).hexdigest()[:16]
    with _get_conn() as conn:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO image_urls (url_hash, url_preview, player, source, used_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (h, filename, player, "file", datetime.now().isoformat())
            )
            conn.commit()
        except Exception:
            pass


def get_used_image_filenames(player: str, hours: int = 168) -> set[str]:
    """Retorna filenames de imagens usadas nas últimas `hours` horas para este jogador."""
    norm_player = _normalize_string(player)
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT url_preview FROM image_urls WHERE player = ? AND source = 'file' AND used_at > ?",
            (norm_player, cutoff)
        ).fetchall()
    return {r[0] for r in rows}


def is_duplicate_image_url(url: str, hours: int = 168) -> bool:
    """Retorna True se esta URL de imagem foi usada nos últimos `hours` horas."""
    h = hashlib.sha256(url.encode()).hexdigest()[:16]
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM image_urls WHERE url_hash = ? AND used_at > ?",
            (h, cutoff)
        ).fetchone()
    return row is not None


def register_image_url(url: str, player: str = "", source: str = "") -> None:
    """Registra URL de imagem como usada para evitar repetição."""
    h = hashlib.sha256(url.encode()).hexdigest()[:16]
    with _get_conn() as conn:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO image_urls (url_hash, url_preview, player, source, used_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (h, url[:200], player, source, datetime.now().isoformat())
            )
            conn.commit()
        except Exception:
            pass


def get_recent_posts(hours: int = 48) -> list[dict]:
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT post_type, player, description, published_at, ig_post_id "
            "FROM posts WHERE published_at > ? ORDER BY published_at DESC",
            (cutoff,)
        ).fetchall()
    return [
        {"post_type": r[0], "player": r[1], "description": r[2],
         "published_at": r[3], "ig_post_id": r[4]}
        for r in rows
    ]
