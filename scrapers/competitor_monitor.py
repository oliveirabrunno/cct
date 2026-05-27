"""
Monitor de concorrentes e trends de tênis para @cafecomteniss.

Estratégia: monitorar via Google News RSS + hashtags públicas para identificar
temas em alta que concorrentes estão cobrindo, sem violar ToS do Instagram.

Concorrentes monitorados via busca de notícias e posts públicos indexados pelo Google.
"""

import hashlib
from datetime import datetime, timedelta, timezone
from collections import Counter

import feedparser

from utils.logger import get_logger

log = get_logger(__name__)

# Contas concorrentes — usadas como contexto de busca, não scraping direto
COMPETITOR_ACCOUNTS = [
    "atptour",
    "rolandgarros",
    "wimbledon",
    "tennistv",
    "tennisontennis",
    "umtenis",          # conta BR de tênis
    "tenisbrasileiro",
]

# Hashtags de tênis a monitorar via Google News
TENNIS_HASHTAGS = [
    "rolandgarros 2026",
    "joao fonseca tennis",
    "bia haddad tennis",
    "sinner alcaraz tennis",
    "ATP WTA tennis",
]

# Jogadores top — se mencionados em múltiplas fontes, é sinal de trend
TOP_PLAYERS = [
    "Jannik Sinner", "Carlos Alcaraz", "Novak Djokovic", "Alexander Zverev",
    "João Fonseca", "Beatriz Haddad Maia", "Iga Swiatek", "Aryna Sabalenka",
    "Coco Gauff", "Daniil Medvedev", "Taylor Fritz", "Alex de Minaur",
    "Félix Auger-Aliassime", "Ben Shelton",
]

# Palavras-chave que indicam conteúdo de alto engajamento para carrossel
CAROUSEL_TRIGGERS = [
    "recorde", "record", "histórico", "historic", "nunca antes", "primeira vez",
    "first time", "upset", "zebra", "surpreend", "inacreditável", "viral",
    "quebrou", "broke", "título", "title", "campeão", "champion",
    "lesão", "injury", "retire", "aposentou", "wild card",
    "final", "semifinal", "quarterfinal", "rodada final",
]


def _build_rss_url(query: str) -> str:
    q = query.replace(" ", "+")
    return f"https://news.google.com/rss/search?q={q}&hl=pt-BR&gl=BR&ceid=BR:pt-419"


def _parse_published(entry) -> datetime | None:
    try:
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    except Exception:
        return None


def _slug(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


class CompetitorMonitor:

    def get_trending_topics(self, hours: int = 6) -> list[dict]:
        """
        Busca os temas de tênis mais mencionados nas últimas `hours` horas
        via Google News RSS. Retorna lista ordenada por urgência.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        all_articles: list[dict] = []

        for query in TENNIS_HASHTAGS:
            url = _build_rss_url(query)
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    pub = _parse_published(entry)
                    if pub is None or pub <= cutoff:
                        continue
                    all_articles.append({
                        "title": entry.get("title", ""),
                        "summary": entry.get("summary", ""),
                        "link": entry.get("link", ""),
                        "published": pub.isoformat(),
                        "query": query,
                    })
            except Exception as e:
                log.warning(f"RSS falhou para '{query}': {e}")

        log.info(f"CompetitorMonitor: {len(all_articles)} artigos nas últimas {hours}h")
        return self._score_articles(all_articles)

    def get_competitor_themes(self, hours: int = 12) -> list[dict]:
        """
        Busca temas que os concorrentes estão cobrindo via Google News
        (pesquisa '{account} tennis' para encontrar conteúdo indexado).
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        themes: list[dict] = []

        for account in COMPETITOR_ACCOUNTS:
            query = f"{account} tennis instagram"
            url = _build_rss_url(query)
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:5]:
                    pub = _parse_published(entry)
                    if pub is None or pub <= cutoff:
                        continue
                    themes.append({
                        "title": entry.get("title", ""),
                        "link": entry.get("link", ""),
                        "published": pub.isoformat(),
                        "competitor_account": account,
                        "source": "google_news_competitor",
                    })
            except Exception as e:
                log.debug(f"Busca de concorrente '{account}' falhou: {e}")

        log.info(f"CompetitorMonitor: {len(themes)} temas de concorrentes")
        return themes

    def score_content_opportunity(self, topics: list[dict]) -> list[dict]:
        """
        Recebe a lista de tópicos e retorna ordenada pela oportunidade de conteúdo.
        Pontuação: urgência + gatilhos de engajamento + jogador prioritário.
        """
        for topic in topics:
            score = topic.get("mention_count", 1)
            title_lower = topic.get("topic", "").lower()
            text = (topic.get("topic", "") + " " + topic.get("raw_summary", "")).lower()

            # Bônus por gatilhos de engajamento
            for trigger in CAROUSEL_TRIGGERS:
                if trigger in text:
                    score += 2

            # Bônus por jogadores prioritários
            if any(p.lower() in text for p in ["fonseca", "haddad", "bia"]):
                score += 3  # brasileiro = prioridade máxima
            elif any(p.lower() in text for p in ["sinner", "alcaraz", "djokovic", "swiatek"]):
                score += 2  # top 4 do mundo

            # Bônus por Roland Garros (torneio atual)
            if any(t in text for t in ["roland garros", "roland-garros", "paris"]):
                score += 2

            topic["opportunity_score"] = score

        return sorted(topics, key=lambda x: x.get("opportunity_score", 0), reverse=True)

    def _score_articles(self, articles: list[dict]) -> list[dict]:
        """
        Agrupa artigos por tema (jogador mencionado), conta menções e
        cria oportunidades de conteúdo ranqueadas.
        """
        player_mentions: Counter = Counter()
        player_articles: dict[str, list[dict]] = {}

        for article in articles:
            title = article.get("title", "")
            summary = article.get("summary", "")
            text = (title + " " + summary).lower()

            for player in TOP_PLAYERS:
                if player.lower().split()[-1] in text or player.lower().split()[0] in text:
                    player_mentions[player] += 1
                    if player not in player_articles:
                        player_articles[player] = []
                    player_articles[player].append(article)

        results: list[dict] = []
        for player, count in player_mentions.most_common(10):
            arts = player_articles.get(player, [])
            latest = max(arts, key=lambda a: a.get("published", ""), default={})

            # Determinar urgência baseado em count e recência
            if count >= 3:
                urgency = "now"
            elif count >= 2:
                urgency = "today"
            else:
                urgency = "this_week"

            # Tipo de conteúdo sugerido
            combined_text = " ".join(a.get("title", "") for a in arts).lower()
            if any(t in combined_text for t in ["vs", "contra", "final", "semifinal"]):
                content_angle = "carousel"  # H2H / match preview
            elif any(t in combined_text for t in ["recorde", "record", "histórico", "nunca"]):
                content_angle = "stat_card"
            elif count >= 3:
                content_angle = "carousel"
            else:
                content_angle = "stat_card"

            results.append({
                "topic": player,
                "source": "google_news",
                "mention_count": count,
                "urgency": urgency,
                "content_angle": content_angle,
                "latest_article": latest.get("title", ""),
                "latest_link": latest.get("link", ""),
                "raw_summary": " | ".join(a.get("title", "") for a in arts[:3]),
                "topic_slug": _slug(player),
            })

        return results
