import requests
from datetime import datetime
from utils.logger import get_logger

log = get_logger(__name__)

HEADERS = {"User-Agent": "CafeComTenis/1.0 (Instagram content bot; contact: cafecomtenis@gmail.com)"}
SUBREDDIT_URL = "https://www.reddit.com/r/tennis/hot.json?limit=50"


def fetch_hot_posts(min_score: int = 300, max_age_hours: int = 24) -> list[dict]:
    try:
        response = requests.get(SUBREDDIT_URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        log.error(f"Reddit fetch falhou: {e}")
        return []

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
