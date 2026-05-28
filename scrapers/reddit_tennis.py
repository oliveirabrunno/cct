import feedparser
import requests
from datetime import datetime, timezone
from utils.logger import get_logger

log = get_logger(__name__)

# Reddit bloqueou bots em 2024 — JSON API retorna 403 mesmo com UA "honesto".
# Solução: usar feed RSS público (.rss) que continua acessível.
# Trade-off: RSS não retorna score nem num_comments, só title/link/timestamp.
SUBREDDIT_RSS = "https://www.reddit.com/r/tennis/hot/.rss"
SUBREDDIT_JSON = "https://www.reddit.com/r/tennis/hot.json?limit=50"

# UA "browser-like" — Reddit bloqueia coisas com "bot" no nome
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": BROWSER_UA}


def _fetch_via_rss(max_age_hours: int) -> list[dict]:
    """Fallback via RSS — não tem score mas tem título/data."""
    try:
        feed = feedparser.parse(SUBREDDIT_RSS, request_headers=HEADERS)
    except Exception as e:
        log.error(f"Reddit RSS falhou: {e}")
        return []

    now_utc = datetime.now(timezone.utc)
    results = []
    for entry in feed.entries[:50]:
        try:
            pub = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        except Exception:
            continue
        age_hours = (now_utc - pub).total_seconds() / 3600
        if age_hours > max_age_hours:
            continue
        title = entry.get("title", "")
        results.append({
            "title": title,
            "title_lower": title.lower(),
            "score": 0,  # RSS não expõe score — placeholder
            "url": entry.get("link", ""),
            "age_hours": round(age_hours, 1),
            "num_comments": 0,
            "flair": "",
        })
    return results


def fetch_hot_posts(min_score: int = 300, max_age_hours: int = 24) -> list[dict]:
    # Tentativa 1: JSON API (tem score, mais útil)
    try:
        response = requests.get(SUBREDDIT_JSON, headers=HEADERS, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        log.warning(f"Reddit JSON falhou ({e}) — tentando RSS")
        results = _fetch_via_rss(max_age_hours)
        log.info(f"Reddit RSS fallback: {len(results)} posts nas últimas {max_age_hours}h")
        return results

    posts = data.get("data", {}).get("children", [])
    now = datetime.now().timestamp()
    results = []

    for child in posts:
        p = child.get("data", {})
        age_hours = (now - p.get("created_utc", now)) / 3600

        if p.get("score", 0) < min_score:
            continue
        if age_hours > max_age_hours:
            continue

        results.append({
            "title": p.get("title", ""),
            "title_lower": p.get("title", "").lower(),
            "score": p.get("score", 0),
            "url": f"https://reddit.com{p.get('permalink', '')}",
            "age_hours": round(age_hours, 1),
            "num_comments": p.get("num_comments", 0),
            "flair": p.get("link_flair_text", ""),
        })

    log.info(f"Reddit: {len(results)} posts com score >= {min_score} nas últimas {max_age_hours}h")
    return results


def search_posts(terms: list[str], min_score: int = 200) -> list[dict]:
    posts = fetch_hot_posts(min_score=min_score)
    return [p for p in posts if any(t in p["title_lower"] for t in terms)]
