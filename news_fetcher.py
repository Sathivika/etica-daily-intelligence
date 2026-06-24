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

# ── Categories & their RSS search queries (ordered for email layout) ─────────
CATEGORIES = {
    "Indian Stock Market":      "Indian stock market Nifty Sensex BSE NSE index sectors",
    "Global Markets":           "global markets S&P500 Dow Jones NASDAQ US Fed India impact",
    "Geopolitics & Trade":      "geopolitics trade war tariffs India US China sanctions",
    "Mutual Funds":             "mutual funds SIP India AMC SEBI NFO new fund offer",
    "Commodities & Currency":   "crude oil gold silver commodity prices India rupee dollar forex",
    "Economy & Policy":         "RBI monetary policy India economy GDP inflation budget fiscal",
    "Health & Term Insurance":  "health insurance term insurance IRDAI India life cover premium claim",
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
      { category_name: [{"title":..., "link":..., "published":..., "source":...}, ...] }
    Order of keys matches the desired email layout.
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


# ── Market Snapshot ───────────────────────────────────────────────────────────

def _fallback(label: str) -> dict:
    return {"label": label, "price": "—", "change": "—", "pct_change": "—", "direction": "neutral"}


def _yf_card(label: str, ticker: str, unit: str = "", decimals: int = 2) -> dict:
    """Fetch a single card from Yahoo Finance via yfinance."""
    import yfinance as yf
    info  = yf.Ticker(ticker).fast_info
    price = info.last_price
    prev  = info.previous_close
    chg   = price - prev
    pct   = (chg / prev) * 100
    fmt   = f"{{:,.{decimals}f}}"
    return {
        "label":      label,
        "price":      f"{unit}{fmt.format(price)}",
        "change":     f"{'+' if chg >= 0 else ''}{fmt.format(chg)}",
        "pct_change": f"{pct:+.2f}%",
        "direction":  "up" if chg >= 0 else "down",
    }


def _ibja_cards() -> tuple[dict, dict]:
    """
    Scrape Gold 999 (₹/10g) and Silver 999 (₹/kg) from ibjarates.com.
    Returns (gold_card, silver_card). Day-over-day change uses the
    two most recent dates in the AM rate table on the page.
    Falls back to dashes on any error.
    """
    import re
    import requests
    from bs4 import BeautifulSoup

    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; EticaBot/1.0)"}
        resp = requests.get("https://ibjarates.com/", headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # The historical rate table contains rows like:
        # | 19/06/2026 | 144941 | 144361 | 132766 | 108706 | 84791 | 230982 | 59214 |
        # Columns: Date | Gold999 | Gold995 | Gold916 | Gold750 | Gold585 | Silver999 | Platinum999
        rows = []
        for tr in soup.find_all("tr"):
            tds = [td.get_text(strip=True) for td in tr.find_all("td")]
            # Valid data row: first cell looks like a date DD/MM/YYYY
            if tds and re.match(r"\d{2}/\d{2}/\d{4}", tds[0]) and len(tds) >= 7:
                rows.append(tds)

        if len(rows) < 2:
            logger.warning("IBJA: Not enough rows to compute day-over-day change.")
            return _fallback("Gold 999 (₹/10g)"), _fallback("Silver 999 (₹/kg)")

        # rows[0] = today/latest, rows[1] = previous trading day
        def parse(val: str) -> float:
            return float(val.replace(",", "").strip())

        gold_today  = parse(rows[0][1])   # Gold 999
        gold_prev   = parse(rows[1][1])
        silver_today = parse(rows[0][6])  # Silver 999
        silver_prev  = parse(rows[1][6])

        def _card(label: str, today: float, prev: float, unit: str = "₹") -> dict:
            chg = today - prev
            pct = (chg / prev) * 100
            return {
                "label":      label,
                "price":      f"{unit}{today:,.0f}",
                "change":     f"{'+' if chg >= 0 else ''}{chg:,.0f}",
                "pct_change": f"{pct:+.2f}%",
                "direction":  "up" if chg >= 0 else "down",
            }

        gold_card   = _card("Gold 999 (₹/10g)",  gold_today,   gold_prev)
        silver_card = _card("Silver 999 (₹/kg)", silver_today, silver_prev)
        logger.info(f"IBJA: Gold={gold_today}, Silver={silver_today}")
        return gold_card, silver_card

    except Exception as e:
        logger.warning(f"IBJA scrape failed: {e}")
        return _fallback("Gold 999 (₹/10g)"), _fallback("Silver 999 (₹/kg)")


def fetch_market_snapshot() -> dict:
    """
    Fetches all 10 market snapshot cards:
      - Nifty 50, Sensex, USD/INR, Crude Oil, S&P 500, NASDAQ, Nikkei 225, Hang Seng → yfinance
      - Gold 999, Silver 999 → ibjarates.com (IBJA, official Indian benchmark)
    Falls back to dashes on any individual failure.
    """
    import yfinance as yf  # noqa: F401

    snapshot = {}

    # ── yfinance cards ────────────────────────────────────────────────────
    YF_CARDS = {
        "nifty":   ("Nifty 50",         "^NSEI",    "",  2),
        "sensex":  ("Sensex",           "^BSESN",   "",  2),
        "usdinr":  ("USD/INR",          "USDINR=X", "₹", 4),
        "crude":   ("Crude Oil (WTI)",  "CL=F",     "$", 2),
        "sp500":   ("S&P 500",          "^GSPC",    "",  2),
        "nasdaq":  ("NASDAQ",           "^IXIC",    "",  2),
        "nikkei":  ("Nikkei 225",       "^N225",    "¥", 0),
        "hangseng":("Hang Seng",        "^HSI",     "",  2),
    }
    for key, (label, ticker, unit, decimals) in YF_CARDS.items():
        try:
            snapshot[key] = _yf_card(label, ticker, unit, decimals)
        except Exception as e:
            logger.warning(f"yfinance failed for {label}: {e}")
            snapshot[key] = _fallback(label)

    # ── IBJA cards ────────────────────────────────────────────────────────
    snapshot["gold"], snapshot["silver"] = _ibja_cards()

    return snapshot


# ── Mint General News ─────────────────────────────────────────────────────────

def fetch_mint_news(max_articles: int = 4) -> list[dict]:
    """
    Fetches top general news from Mint via their RSS feed.
    Returns list of {"title", "link", "source", "published"}.
    Falls back to empty list on failure.
    """
    MINT_RSS = "https://www.livemint.com/rss/news"
    try:
        feed = feedparser.parse(MINT_RSS)
        articles = []
        for entry in feed.entries[:max_articles * 3]:  # fetch extra, dedup, then trim
            articles.append({
                "title":     entry.get("title", "No Title"),
                "link":      entry.get("link", "https://www.livemint.com/"),
                "published": entry.get("published", ""),
                "source":    "Mint",
            })
        articles = _deduplicate(articles)[:max_articles]
        logger.info(f"Mint: fetched {len(articles)} articles")
        return articles
    except Exception as e:
        logger.warning(f"Mint RSS fetch failed: {e}")
        return []