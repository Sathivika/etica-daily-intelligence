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
    "Mutual Funds":             "mutual funds SIP India AMC SEBI",
    "Commodities & Currency":   "crude oil gold silver commodity prices India rupee dollar forex",
    "Economy & Policy":         "RBI monetary policy India economy GDP inflation budget fiscal",
    "Health & Term Insurance":  "health insurance term insurance IRDAI India life cover premium claim",
}

# Dedicated NFO query — merged into Mutual Funds to guarantee NFO articles appear
NFO_QUERY = "NFO new fund offer mutual fund India open close date 2025 2026"

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
    Mutual Funds gets a bonus dedicated NFO fetch merged in to guarantee NFO articles appear.
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

        # ── Bonus NFO fetch for Mutual Funds ─────────────────────────────
        if category == "Mutual Funds":
            logger.info("  Fetching bonus NFO articles...")
            nfo_feed = feedparser.parse(_rss_url(NFO_QUERY))
            for entry in nfo_feed.entries[:10]:
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


# ── General News (multi-source) ───────────────────────────────────────────────

def fetch_general_news(max_articles: int = 5) -> list[dict]:
    """
    Fetches top general news from multiple Indian news sources via RSS.
    Sources: Mint, Times of India, NDTV, The Hindu, Economic Times.
    Deduplicates across all sources and returns the top max_articles.
    Falls back gracefully if any individual source fails.
    """
    SOURCES = [
        ("Mint",             "https://www.livemint.com/rss/news"),
        ("Times of India",   "https://timesofindia.indiatimes.com/rssfeedstopstories.cms"),
        ("NDTV",             "https://feeds.feedburner.com/ndtvnews-top-stories"),
        ("The Hindu",        "https://www.thehindu.com/news/national/feeder/default.rss"),
        ("Economic Times",   "https://economictimes.indiatimes.com/rssfeedstopstories.cms"),
    ]

    all_articles = []
    for source_name, rss_url in SOURCES:
        try:
            feed = feedparser.parse(rss_url)
            count = 0
            for entry in feed.entries[:6]:  # up to 6 per source before dedup
                title = entry.get("title", "").strip()
                link  = entry.get("link",  "").strip()
                if not title or not link:
                    continue
                all_articles.append({
                    "title":     title,
                    "link":      link,
                    "published": entry.get("published", ""),
                    "source":    source_name,
                })
                count += 1
            logger.info(f"  General news — {source_name}: {count} articles")
        except Exception as e:
            logger.warning(f"  General news — {source_name} failed: {e}")

    deduped = _deduplicate(all_articles)
    logger.info(f"General news: {len(all_articles)} fetched → {len(deduped)} after dedup → returning top {max_articles}")
    return deduped[:max_articles]


# ── Live NFO Tracker (AMFI Official) ─────────────────────────────────────────

def fetch_live_nfo() -> list[dict]:
    """
    Fetches live/open NFOs from two AMFI sources:
      1. AMFI RSS feed  — gives fund name, fund house, category, launch date
      2. AMFI NFO HTML  — gives open date, close date, SID PDF link

    Returns list of dicts:
      {
        "name":       str,   # Fund name
        "fund_house": str,   # AMC / Fund house
        "category":   str,   # Scheme category
        "open_date":  str,   # NFO open date (DD-MMM-YYYY or "—")
        "close_date": str,   # NFO close date (DD-MMM-YYYY or "—")
        "sid_url":    str,   # SID PDF URL from portal.amfiindia.com or ""
      }
    Falls back to RSS-only data if HTML scrape fails.
    """
    import requests
    from bs4 import BeautifulSoup

    AMFI_RSS  = "https://portal.amfiindia.com/RssNAV.aspx?nfo=y"
    AMFI_HTML = "https://www.amfiindia.com/new-fund-offer"

    headers = {"User-Agent": "Mozilla/5.0 (compatible; EticaBot/1.0)"}

    # ── Step 1: Parse RSS for base NFO list ──────────────────────────────
    rss_nfos = {}
    try:
        feed = feedparser.parse(AMFI_RSS)
        for entry in feed.entries:
            name = entry.get("title", "").strip()
            if not name:
                continue
            # Parse embedded HTML table in description for fund_house, category, launch_date
            desc_html = entry.get("description", "")
            soup = BeautifulSoup(desc_html, "html.parser")
            rows = soup.find_all("tr")
            details = {}
            for row in rows:
                tds = row.find_all("td")
                if len(tds) == 2:
                    key = tds[0].get_text(strip=True).lower()
                    val = tds[1].get_text(strip=True)
                    if "mutual fund" in key:
                        details["fund_house"] = val
                    elif "category" in key:
                        details["category"] = val
                    elif "launch" in key or "date" in key:
                        details["launch_date"] = val

            rss_nfos[name.lower()] = {
                "name":       name,
                "fund_house": details.get("fund_house", "—"),
                "category":   details.get("category", "—"),
                "launch_date":details.get("launch_date", "—"),
                "open_date":  "—",
                "close_date": "—",
                "sid_url":    "",
            }
        logger.info(f"AMFI RSS: {len(rss_nfos)} NFOs found")
    except Exception as e:
        logger.warning(f"AMFI RSS parse failed: {e}")

    # ── Step 2: Scrape AMFI HTML for open/close dates and SID links ──────
    try:
        resp = requests.get(AMFI_HTML, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # AMFI NFO page has a table with columns:
        # Scheme Name | Open Date | Close Date | Scheme Type | SID
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) < 3:
                    continue
                texts = [c.get_text(strip=True) for c in cells]
                # Try to find SID link in any cell
                sid_url = ""
                for cell in cells:
                    a = cell.find("a", href=True)
                    if a and "portal.amfiindia.com" in a["href"] and ".pdf" in a["href"]:
                        sid_url = a["href"]
                        break
                    elif a and "spages" in str(a.get("href", "")):
                        href = a["href"]
                        if not href.startswith("http"):
                            href = "https://portal.amfiindia.com" + href
                        sid_url = href
                        break

                # Match row to an RSS NFO by name fuzzy match
                scheme_name = texts[0].strip().lower()
                if not scheme_name:
                    continue

                for key in rss_nfos:
                    if _similar(key, scheme_name) > 0.75:
                        # Try to extract dates — look for DD-Mon-YYYY pattern
                        import re
                        date_pat = re.compile(r'\d{2}-[A-Za-z]{3}-\d{4}')
                        dates = []
                        for t in texts[1:]:
                            m = date_pat.search(t)
                            if m:
                                dates.append(m.group())
                        if len(dates) >= 2:
                            rss_nfos[key]["open_date"]  = dates[0]
                            rss_nfos[key]["close_date"] = dates[1]
                        elif len(dates) == 1:
                            rss_nfos[key]["open_date"] = dates[0]
                        if sid_url:
                            rss_nfos[key]["sid_url"] = sid_url
                        break

        logger.info("AMFI HTML: open/close dates and SID links extracted")
    except Exception as e:
        logger.warning(f"AMFI HTML scrape failed (using RSS data only): {e}")

    # ── Step 3: Fill missing close dates using launch_date as fallback ───
    result = []
    for nfo in rss_nfos.values():
        if nfo["close_date"] == "—" and nfo.get("launch_date") and nfo["launch_date"] != "—":
            # launch_date from RSS is the NFO open/launch date
            nfo["open_date"] = nfo.get("launch_date", "—")
        nfo.pop("launch_date", None)
        result.append(nfo)

    logger.info(f"Live NFO tracker: {len(result)} NFOs ready")
    return result