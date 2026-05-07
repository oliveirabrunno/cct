from scrapers.google_news import fetch_recent_news
from scrapers.reddit_tennis import fetch_hot_posts
from utils.logger import get_logger

log = get_logger(__name__)

TREND_THRESHOLD = 4

MONITORED_PLAYERS = {
    "João Fonseca":      ["joao fonseca", "joão fonseca", "fonseca tennis"],
    "Jannik Sinner":     ["sinner", "jannik sinner"],
    "Carlos Alcaraz":    ["alcaraz", "carlos alcaraz", "carlitos"],
    "Iga Swiatek":       ["swiatek", "iga swiatek"],
    "Aryna Sabalenka":   ["sabalenka", "aryna sabalenka"],
    "Novak Djokovic":    ["djokovic", "novak djokovic"],
    "Beatriz Haddad":    ["bia haddad", "beatriz haddad", "haddad maia"],
    "Coco Gauff":        ["gauff", "coco gauff"],
    "Daniil Medvedev":   ["medvedev", "daniil medvedev"],
    "Alexander Zverev":  ["zverev", "alexander zverev"],
    "Casper Ruud":       ["ruud", "casper ruud"],
    "Taylor Fritz":      ["fritz", "taylor fritz"],
    "Ben Shelton":       ["shelton", "ben shelton"],
    "Elena Rybakina":    ["rybakina", "elena rybakina"],
    "Jessica Pegula":    ["pegula", "jessica pegula"],
    "Madison Keys":      ["keys", "madison keys"],
    "Jasmine Paolini":   ["paolini", "jasmine paolini"],
}


class TrendDetector:

    async def check_all_players(self) -> list[dict]:
        recent_news = fetch_recent_news(hours=6)
        reddit_posts = fetch_hot_posts(min_score=500, max_age_hours=12)

        trending = []

        for player_name, search_terms in MONITORED_PLAYERS.items():
            score = 0
            signals = {}

            news_count = self._count_news_mentions(recent_news, search_terms)
            news_score = min(news_count, 5)
            score += news_score
            signals["news_count"] = news_count

            reddit_hit = self._check_reddit_mentions(reddit_posts, search_terms)
            if reddit_hit:
                score += 3
                signals["reddit_post"] = reddit_hit

            if score >= TREND_THRESHOLD:
                trending.append({
                    "player": player_name,
                    "score": score,
                    "signals": signals,
                    "news": [
                        a for a in recent_news
                        if any(t in a["title_lower"] for t in search_terms)
                    ][:3],
                })
                log.info(f"TREND: {player_name} (score: {score})")

        return sorted(trending, key=lambda x: x["score"], reverse=True)

    def _count_news_mentions(self, articles: list, terms: list) -> int:
        count = 0
        for article in articles:
            text = article["title_lower"] + " " + article.get("summary_lower", "")
            if any(t in text for t in terms):
                count += 1
        return count

    def _check_reddit_mentions(self, posts: list, terms: list) -> dict | None:
        for post in posts:
            if any(t in post["title_lower"] for t in terms):
                return post
        return None
