"""
Deduplicação de posts via SQLite.
Evita publicar o mesmo conteúdo duas vezes nas últimas 72h.
"""

import hashlib
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from utils.logger import get_logger

log = get_logger(__name__)

DB_PATH = Path("data/database.sqlite")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


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


def content_hash(post_type: str, player: str, extra: str = "") -> str:
    raw = f"{post_type}:{player.lower().strip()}:{extra.lower().strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def is_duplicate(post_type: str, player: str, extra: str = "", hours: int = 72) -> bool:
    h = content_hash(post_type, player, extra)
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

    with _get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM posts WHERE content_hash = ? AND published_at > ?",
            (h, cutoff)
        ).fetchone()

    if row:
        log.info(f"Duplicado detectado: {post_type}/{player} (hash {h})")
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


def register_used_image(player: str, filename: str) -> None:
    """Registra arquivo de imagem como usado (evita repetição por 7 dias)."""
    key = f"{player.lower().strip()}::{filename}"
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
    prefix = f"{player.lower().strip()}::"
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT url_preview FROM image_urls WHERE player = ? AND source = 'file' AND used_at > ?",
            (player, cutoff)
        ).fetchall()
    return {r[0] for r in rows}


def is_duplicate_image_url(url: str, hours: int = 168) -> bool:
    """Retorna True se esta URL de imagem foi usada nos últimos `hours` horas (padrão: 7 dias)."""
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
