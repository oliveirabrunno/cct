import feedparser
from datetime import datetime, timedelta
from utils.logger import get_logger

log = get_logger(__name__)

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=tennis+ATP+WTA&hl=pt-BR&gl=BR&ceid=BR:pt-419",
    "https://news.google.com/rss/search?q=tenis&hl=pt-BR&gl=BR&ceid=BR:pt-419",
    "https://news.google.com/rss/search?q=joao+fonseca+tennis&hl=pt-BR&gl=BR&ceid=BR:pt-419",
]


def fetch_recent_news(hours: int = 6) -> list[dict]:
    cutoff = datetime.now() - timedelta(hours=hours)
    articles = []

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                try:
                    published = datetime(*entry.published_parsed[:6])
                except Exception:
                    continue

                if published <= cutoff:
                    continue

                articles.append({
                    "title": entry.title,
                    "title_lower": entry.title.lower(),
                    "summary": getattr(entry, "summary", ""),
                    "summary_lower": getattr(entry, "summary", "").lower(),
                    "link": entry.link,
                    "published": published.isoformat(),
                    "source": feed.feed.get("title", "Google News"),
                })
        except Exception as e:
            log.error(f"Erro ao processar feed {url}: {e}")

    log.info(f"Google News: {len(articles)} artigos nas últimas {hours}h")
    return articles


def search_news(query: str, hours: int = 24) -> list[dict]:
    url = (
        f"https://news.google.com/rss/search"
        f"?q={query.replace(' ', '+')}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    )
    cutoff = datetime.now() - timedelta(hours=hours)
    articles = []

    try:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            try:
                published = datetime(*entry.published_parsed[:6])
            except Exception:
                continue
            if published <= cutoff:
                continue
            articles.append({
                "title": entry.title,
                "summary": getattr(entry, "summary", ""),
                "link": entry.link,
                "published": published.isoformat(),
            })
    except Exception as e:
        log.error(f"Erro ao buscar '{query}': {e}")

    return articles
