"""
news_fetcher.py
Fetches news from Google News RSS feeds for each category.
Removes duplicate articles based on title similarity.
"""

import feedparser
import logging
from datetime import datetime, timezone
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# ── Categories & their RSS search queries ────────────────────────────────────
CATEGORIES = {
    "Indian Stock Market": "Indian stock market Nifty Sensex BSE NSE",
    "Global Markets":      "global markets S&P500 Dow Jones NASDAQ",
    "Mutual Funds":        "mutual funds SIP India AMC SEBI",
    "Economy & Policy":    "RBI monetary policy India economy GDP inflation",
    "Banking & Finance":   "Indian banking sector HDFC ICICI SBI NPA",
    "Commodities":         "crude oil gold silver commodity prices India",
    "Geopolitics & Trade": "geopolitics trade war tariffs India US China",
}

ARTICLES_PER_CATEGORY = 20
SIMILARITY_THRESHOLD   = 0.70   # titles more similar than this → duplicate


def _rss_url(query: str) -> str:
    encoded = query.replace(" ", "+")
    return f"https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en"


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _deduplicate(articles: list[dict]) -> list[dict]:
    unique = []
    for article in articles:
        is_dup = any(
            _similar(article["title"], seen["title"]) >= SIMILARITY_THRESHOLD
            for seen in unique
        )
        if not is_dup:
            unique.append(article)
    return unique


def fetch_all_news() -> dict[str, list[dict]]:
    """
    Returns a dict:
      { category_name: [{"title":..., "link":..., "published":...}, ...] }
    """
    all_news: dict[str, list[dict]] = {}

    for category, query in CATEGORIES.items():
        logger.info(f"Fetching: {category}")
        url  = _rss_url(query)
        feed = feedparser.parse(url)

        articles = []
        for entry in feed.entries[:ARTICLES_PER_CATEGORY]:
            articles.append({
                "title":     entry.get("title", "No Title"),
                "link":      entry.get("link",  "#"),
                "published": entry.get("published", ""),
                "source":    entry.get("source", {}).get("title", ""),
            })

        before = len(articles)
        articles = _deduplicate(articles)
        logger.info(f"  {before} fetched → {len(articles)} after dedup")

        all_news[category] = articles

    total = sum(len(v) for v in all_news.values())
    logger.info(f"Total unique articles: {total}")
    return all_news
