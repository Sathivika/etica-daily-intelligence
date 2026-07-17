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

# Dedicated Fed query — merged into Global Markets to guarantee Fed/FOMC articles appear
FED_QUERY = "Federal Reserve FOMC interest rate decision US jobs report monetary policy Powell"

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


def _is_fresh(published: str, max_age_days: int = 3) -> bool:
    """Returns True if the article was published within max_age_days. Accepts articles with no date."""
    if not published:
        return True  # no date = keep (can't tell, better safe)
    import email.utils
    try:
        parsed = email.utils.parsedate_to_datetime(published)
        from datetime import timezone
        age = datetime.now(timezone.utc) - parsed
        return age.days <= max_age_days
    except Exception:
        return True  # unparseable date = keep


def fetch_all_news() -> dict[str, list[dict]]:
    """
    Returns a dict:
      { category_name: [{"title":..., "link":..., "published":..., "source":...}, ...] }
    Order of keys matches the desired email layout.
    Mutual Funds gets a bonus dedicated NFO fetch merged in to guarantee NFO articles appear.
    Stale articles (older than 3 days) are filtered out to prevent Groq hallucinating old events.
    Cross-category deduplication: articles already seen in a previous category are skipped.
    """
    all_news: dict[str, list[dict]] = {}
    seen_titles_global: list[str] = []  # tracks titles across ALL categories

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

        # ── Bonus Fed/FOMC fetch for Global Markets ──────────────────────
        if category == "Global Markets":
            logger.info("  Fetching bonus Federal Reserve / FOMC articles...")
            fed_feed = feedparser.parse(_rss_url(FED_QUERY))
            for entry in fed_feed.entries[:10]:
                articles.append({
                    "title":     entry.get("title", "No Title"),
                    "link":      entry.get("link",  "#"),
                    "published": entry.get("published", ""),
                    "source":    entry.get("source", {}).get("title", ""),
                })

        # ── Cross-category dedup: remove articles already in a previous category ──
        articles = [
            a for a in articles
            if not any(_similar(a["title"], seen) >= SIMILARITY_THRESHOLD for seen in seen_titles_global)
        ]

        before = len(articles)
        articles = _deduplicate(articles)

        # ── Filter stale articles ─────────────────────────────────────────
        fresh = [a for a in articles if _is_fresh(a["published"])]
        stale_count = len(articles) - len(fresh)
        if stale_count:
            logger.info(f"  Dropped {stale_count} stale article(s) (>3 days old)")
        articles = fresh if fresh else articles  # fallback: keep all if everything is stale

        logger.info(f"  {before} fetched → {len(articles)} after dedup+freshness")

        # Register all kept titles globally to prevent repeats in later categories
        seen_titles_global.extend(a["title"] for a in articles)

        all_news[category] = articles

    total = sum(len(v) for v in all_news.values())
    logger.info(f"Total unique articles: {total}")
    return all_news


# ── Market Snapshot ───────────────────────────────────────────────────────────

def _fallback(label: str) -> dict:
    return {"label": label, "price": "—", "change": "—", "pct_change": "—", "direction": "neutral"}


def _yf_card(label: str, ticker: str, unit: str = "", decimals: int = 2) -> dict:
    """
    Fetch a single card from Yahoo Finance via yfinance.
    Always uses PREVIOUS DAY closing price (previous_close vs the day before that),
    so the newsletter shows accurate closing data regardless of when it runs.
    """
    import yfinance as yf
    ticker_obj = yf.Ticker(ticker)
    info = ticker_obj.fast_info

    # previous_close = yesterday closing price (what we want to show)
    # We compute change vs the day before yesterday using history
    price = info.previous_close  # yesterday's close
    try:
        hist  = ticker_obj.history(period="5d")
        if len(hist) >= 2:
            prev = hist["Close"].iloc[-2]  # day before yesterday
        else:
            prev = info.previous_close
    except Exception:
        prev = info.previous_close

    chg = price - prev
    pct = (chg / prev) * 100 if prev else 0
    fmt = f"{{:,.{decimals}f}}"
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


def _investing_bond10y() -> dict | None:
    """
    Scrapes India's 10Y Govt Bond closing yield from investing.com's historical
    data table (most recent trading day's close vs. the prior trading day's close).
    Returns None if the table can't be parsed (site structure changed, blocked, etc.).
    """
    import requests
    from bs4 import BeautifulSoup

    url = "https://in.investing.com/rates-bonds/india-10-year-bond-yield-historical-data"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept-Language": "en-IN,en;q=0.9",
    }
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    def parse_num(v: str):
        v = v.replace(",", "").replace("%", "").strip()
        try:
            return float(v)
        except ValueError:
            return None

    # Historical-data table rows are date-ordered, most recent first.
    # Column layout: Date | Price(close) | Open | High | Low | Change %
    closes = []
    for tr in soup.find_all("tr"):
        tds = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(tds) < 2:
            continue
        price = parse_num(tds[1])
        if price is not None and 0 < price < 25:  # sane bond-yield range
            closes.append(price)

    if len(closes) < 2:
        return None

    latest, prev = closes[0], closes[1]
    chg = latest - prev
    pct = (chg / prev) * 100 if prev else 0
    return {
        "label":      "10Y Govt Bond",
        "price":      f"{latest:.3f}%",
        "change":     f"{'+' if chg >= 0 else ''}{chg:.3f}",
        "pct_change": f"{pct:+.2f}%",
        "direction":  "up" if chg >= 0 else "down",
    }


def _tradingeconomics_bond10y() -> dict | None:
    """
    Fallback scraper: reads the Actual/Previous summary stats table on
    tradingeconomics.com's India 10Y bond yield page.
    Returns None if the table can't be found/parsed.
    """
    import requests
    from bs4 import BeautifulSoup

    url = "https://in.investing.com/rates-bonds/india-10-year-bond-yield-historical-data"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; EticaBot/1.0)"}
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        header_idx, headers_lower = None, []
        for i, row in enumerate(rows):
            cells = [c.get_text(strip=True).lower() for c in row.find_all(["th", "td"])]
            if "actual" in cells and "previous" in cells:
                header_idx, headers_lower = i, cells
                break
        if header_idx is None:
            continue

        idx_actual = headers_lower.index("actual")
        idx_prev   = headers_lower.index("previous")
        for row in rows[header_idx + 1:]:
            cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
            if len(cells) <= max(idx_actual, idx_prev):
                continue
            try:
                actual = float(cells[idx_actual])
                prev   = float(cells[idx_prev])
            except ValueError:
                continue
            chg = actual - prev
            pct = (chg / prev) * 100 if prev else 0
            return {
                "label":      "10Y Govt Bond",
                "price":      f"{actual:.2f}%",
                "change":     f"{'+' if chg >= 0 else ''}{chg:.2f}",
                "pct_change": f"{pct:+.2f}%",
                "direction":  "up" if chg >= 0 else "down",
            }
    return None


def _bond10y_card() -> dict:
    """
    Fetches India's 10Y Govt Bond closing yield.
    Primary:  investing.com historical-data table (previous trading day's close).
    Fallback: tradingeconomics.com Actual/Previous summary table.
    Falls back to dashes only if both sources fail.
    """
    try:
        card = _investing_bond10y()
        if card:
            logger.info(f"10Y Govt Bond from investing.com: {card['price']}")
            return card
    except Exception as e:
        logger.warning(f"investing.com bond yield scrape failed: {e}")

    try:
        card = _tradingeconomics_bond10y()
        if card:
            logger.info(f"10Y Govt Bond from tradingeconomics.com: {card['price']}")
            return card
    except Exception as e:
        logger.warning(f"tradingeconomics.com bond yield scrape failed: {e}")

    logger.warning("10Y Govt Bond: both sources failed, falling back to dashes")
    return _fallback("10Y Govt Bond")


def fetch_market_snapshot() -> dict:
    """
    Fetches all 10 market snapshot cards:
      - Nifty 50, Sensex, USD/INR, Crude Oil, S&P 500, NASDAQ, Nikkei 225, Hang Seng → yfinance
      - Gold 999, Silver 999 → ibjarates.com (IBJA, official Indian benchmark)
      - 10Y Govt Bond → investing.com (fallback: tradingeconomics.com)
    Falls back to dashes on any individual failure.
    """
    import yfinance as yf  # noqa: F401

    snapshot = {}

    # ── yfinance cards ────────────────────────────────────────────────────
    YF_CARDS = {
        "nifty":    ("Nifty 50",          "^NSEI",    "",  2),
        "sensex":   ("Sensex",            "^BSESN",   "",  2),
        "nifty500": ("Nifty 500",         "^CRSLDX",  "",  2),
        "usdinr":   ("USD/INR",           "USDINR=X", "₹", 4),
        "crude":    ("Crude Oil (WTI)",   "CL=F",     "$", 2),
        "sp500":    ("S&P 500",           "^GSPC",    "",  2),
        "nasdaq":   ("NASDAQ",            "^IXIC",    "",  2),
        "nikkei":   ("Nikkei 225",        "^N225",    "¥", 0),
        "hangseng": ("Hang Seng",         "^HSI",     "",  2),
    }
    for key, (label, ticker, unit, decimals) in YF_CARDS.items():
        try:
            snapshot[key] = _yf_card(label, ticker, unit, decimals)
        except Exception as e:
            logger.warning(f"yfinance failed for {label}: {e}")
            snapshot[key] = _fallback(label)

    # ── 10Y Govt Bond (scraped — yfinance's ^IN10Y is unreliable) ──────────
    snapshot["bond10y"] = _bond10y_card()

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
    Fetches live/open NFOs from AMFI's official RSS feed.
    Returns list of dicts:
      {
        "name":       str,   # Fund name
        "fund_house": str,   # AMC / Fund house
        "category":   str,   # Scheme category
        "open_date":  str,   # NFO open/launch date
        "close_date": str,   # NFO close date (best-effort; "—" if not available)
      }
    Note: AMFI's NFO detail page (open/close dates beyond launch, SID links) is
    JavaScript-rendered and not scrapable without a browser, so this relies on
    the RSS feed plus a best-effort close-date estimate. Full details always
    available via the "View All NFOs on AMFI" button linked in the email.
    """
    AMFI_RSS = "https://portal.amfiindia.com/RssNAV.aspx?nfo=y"

    rss_nfos = {}
    try:
        feed = feedparser.parse(AMFI_RSS)
        for entry in feed.entries:
            name = entry.get("title", "").strip()
            if not name:
                continue
            desc_html = entry.get("description", "")
            from bs4 import BeautifulSoup
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
                    elif "close" in key or "closure" in key:
                        details["close_date"] = val

            rss_nfos[name.lower()] = {
                "name":       name,
                "fund_house": details.get("fund_house", "—"),
                "category":   details.get("category", "—"),
                "open_date":  details.get("launch_date", "—"),
                "close_date": details.get("close_date", "—"),
            }
        logger.info(f"AMFI RSS: {len(rss_nfos)} NFOs found")
    except Exception as e:
        logger.warning(f"AMFI RSS parse failed: {e}")

    result = [{k: v for k, v in nfo.items() if k != "category"} for nfo in rss_nfos.values()]
    logger.info(f"Live NFO tracker: {len(result)} NFOs ready")
    return result

# ── Word of the Day ───────────────────────────────────────────────────────────

# Curated fallback list — rotates daily so it's always fresh even if Groww API is down
_WOTD_FALLBACK = [
    ("SIP",               "Systematic Investment Plan — a method of investing a fixed amount in mutual funds at regular intervals, averaging out market volatility over time."),
    ("NAV",               "Net Asset Value — the per-unit market value of a mutual fund scheme, calculated as total assets minus liabilities divided by outstanding units."),
    ("CAGR",              "Compound Annual Growth Rate — the rate at which an investment grows annually over a specified period, assuming profits are reinvested each year."),
    ("Alpha",             "A measure of an investment's performance relative to a benchmark index. Positive alpha means the fund outperformed; negative means it underperformed."),
    ("Beta",              "A measure of a stock or fund's volatility relative to the market. Beta >1 means more volatile than the market; <1 means less volatile."),
    ("Yield",             "The income generated by an investment, expressed as a percentage of cost or current market value. Includes dividends, interest, or rental income."),
    ("Liquidity",         "How quickly and easily an asset can be converted to cash without significantly affecting its price. Cash is the most liquid asset."),
    ("Hedge",             "An investment made to reduce the risk of adverse price movements in another asset. Like an insurance policy against market losses."),
    ("Arbitrage",         "The simultaneous purchase and sale of an asset in different markets to profit from price differences. It helps keep prices consistent across markets."),
    ("Dividend",          "A portion of a company's profits distributed to shareholders, usually in cash or additional shares, as a reward for holding the stock."),
    ("Bull Market",       "A period of rising stock prices, usually by 20% or more from recent lows, driven by investor optimism and strong economic indicators."),
    ("Bear Market",       "A period of falling stock prices, typically 20% or more from recent highs, driven by pessimism, economic slowdown, or investor fear."),
    ("P/E Ratio",         "Price-to-Earnings Ratio — a valuation metric comparing a company's stock price to its earnings per share. Higher P/E suggests higher growth expectations."),
    ("Market Cap",        "Market Capitalisation — the total market value of a company's outstanding shares. Calculated as share price × number of shares outstanding."),
    ("Diversification",   "Spreading investments across different asset classes, sectors, or geographies to reduce risk. The principle: don't put all eggs in one basket."),
    ("Volatility",        "The degree of variation in a security's price over time. High volatility means large price swings; low volatility means relatively stable prices."),
    ("Rebalancing",       "Realigning the weightings of a portfolio by buying or selling assets to maintain the original desired level of asset allocation and risk."),
    ("Inflation",         "The rate at which the general level of prices for goods and services rises over time, eroding the purchasing power of money."),
    ("Recession",         "A significant decline in economic activity lasting more than two consecutive quarters, marked by falling GDP, employment, and consumer spending."),
    ("Repo Rate",         "The rate at which the RBI lends money to commercial banks. When RBI raises this rate, borrowing becomes costlier, reducing money supply and inflation."),
    ("Sensex",            "The S&P BSE Sensex is a benchmark index tracking 30 financially sound companies listed on the Bombay Stock Exchange, representing the Indian economy."),
    ("Nifty 50",          "The NSE Nifty 50 is India's national stock market index, tracking 50 large-cap companies across 13 sectors listed on the National Stock Exchange."),
    ("FII",               "Foreign Institutional Investor — an entity from outside India investing in Indian securities markets. FII flows are a key indicator of foreign sentiment."),
    ("DII",               "Domestic Institutional Investor — Indian institutions like mutual funds, insurance companies, and banks that invest in domestic securities markets."),
    ("Gilt Fund",         "A mutual fund that invests exclusively in government securities (G-Secs). Considered virtually risk-free in terms of credit risk but sensitive to interest rates."),
    ("ELSS",              "Equity Linked Savings Scheme — a tax-saving mutual fund with a 3-year lock-in period eligible for ₹1.5 lakh deduction under Section 80C of the Income Tax Act."),
    ("Expense Ratio",     "The annual fee charged by a mutual fund to cover operating costs, expressed as a percentage of AUM. Lower expense ratios mean more returns for investors."),
    ("AUM",               "Assets Under Management — the total market value of all investments managed by a fund house or portfolio manager on behalf of their clients."),
    ("NFO",               "New Fund Offer — the first subscription offering when an AMC launches a new mutual fund scheme, similar to an IPO for stocks."),
    ("STT",               "Securities Transaction Tax — a tax levied on the purchase and sale of securities listed on Indian stock exchanges, collected at source."),
    ("LTCG",              "Long-Term Capital Gains tax — tax on profits from selling assets held longer than the specified period: 1 year for equity, 2 years for property."),
    ("STCG",              "Short-Term Capital Gains tax — tax on profits from selling assets held for less than the qualifying long-term period. Rate: 20% for equity."),
    ("Demat Account",     "Dematerialised Account — an account that holds financial securities in electronic form, eliminating the need for physical share certificates."),
    ("Circuit Breaker",   "A regulatory mechanism that temporarily halts trading when an index falls or rises beyond a set percentage, preventing panic-driven crashes."),
    ("Upper Circuit",     "The maximum price limit beyond which a stock cannot trade on a given day, set to prevent excessive speculation and curb runaway price increases."),
    ("Lower Circuit",     "The minimum price limit below which a stock cannot trade on a given day, protecting against panic selling and sharp single-day crashes."),
    ("Bilateral Trade",   "Trade that happens between two countries in goods and/or services. It does not imply equal value exchange — just the trading relationship between them."),
    ("Tariff",            "A tax imposed by a government on imported goods. Tariffs raise the price of foreign products, protecting domestic industries and generating revenue."),
    ("Fiscal Deficit",    "The difference between government revenue and total expenditure when spending exceeds income. Funded by borrowing, it can be inflationary if excessive."),
    ("Current Account",   "A component of a country's balance of payments measuring trade in goods, services, and transfer payments. A deficit means more imports than exports."),
    ("Bond Yield",        "The return an investor earns by holding a bond to maturity. Bond yields move inversely to bond prices — when prices fall, yields rise."),
    ("Duration",          "A measure of a bond's sensitivity to interest rate changes. Higher duration means greater price impact when rates move up or down."),
    ("Credit Rating",     "An evaluation of a borrower's creditworthiness by agencies like CRISIL or ICRA. Ratings range from AAA (safest) to D (default)."),
    ("Sovereign Gold Bond","Government securities denominated in grams of gold, issued by RBI. Investors earn interest plus price appreciation, without physical gold storage risks."),
    ("Mutual Fund",       "A pool of money collected from many investors to invest in securities like stocks, bonds, and money market instruments, managed by professional fund managers."),
    ("Index Fund",        "A passively managed mutual fund that replicates a market index like Nifty 50. Lower cost than active funds; returns mirror the index performance."),
    ("Debt Fund",         "A mutual fund investing primarily in fixed-income instruments like bonds, treasury bills, and debentures. Lower risk than equity; suitable for conservative investors."),
    ("Hybrid Fund",       "A mutual fund that invests in a mix of equity and debt instruments. Balances growth potential with stability; suits moderate-risk investors."),
    ("Asset Allocation",  "Strategy of dividing investments among different asset categories — equity, debt, gold, real estate — based on goals, risk tolerance, and time horizon."),
    ("Exit Load",         "A fee charged when an investor redeems mutual fund units before a specified period. Meant to discourage short-term trading in long-term funds."),
    ("Lock-in Period",    "A fixed duration during which an investor cannot redeem or sell their investment. Common in ELSS (3 years) and PPF (15 years)."),
    ("Benchmark Index",   "A standard against which a mutual fund's performance is measured. For large-cap funds, the Nifty 50 or Sensex are common benchmarks."),
    ("Rupee Cost Averaging","An investment strategy where a fixed amount is invested regularly regardless of price, buying more units when prices are low and fewer when high."),
    ("Corpus",            "The total accumulated value of an investment or savings pool. Often used to refer to the retirement fund or education fund one aims to build."),
    ("Folio Number",      "A unique identification number assigned to a mutual fund investor. One folio can hold multiple schemes from the same fund house."),
    ("KYC",               "Know Your Customer — a mandatory process for verifying the identity and address of investors before allowing them to transact in financial markets."),
    ("SEBI",              "Securities and Exchange Board of India — the regulatory body that oversees India's securities markets, protects investor interests, and regulates market participants."),
    ("IRDAI",             "Insurance Regulatory and Development Authority of India — the statutory body that regulates and supervises the insurance industry in India."),
    ("RBI",               "Reserve Bank of India — India's central bank that controls monetary policy, regulates banks, manages foreign exchange, and issues currency."),
]

def fetch_word_of_the_day() -> dict:
    """
    Fetches Word of the Day from Groww's internal API.
    Falls back to a curated daily-rotating list of 60+ finance terms if Groww is unreachable.
    Returns: {"word": str, "definition": str, "source": str}
    """
    import requests
    from datetime import date

    # Try Groww's internal digest API (used by their frontend)
    GROWW_ENDPOINTS = [
        "https://groww.in/v1/api/digest/v2/word-of-the-day",
        "https://groww.in/v1/api/digest/word-of-the-day",
        "https://groww.in/v1/api/wotd/today",
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://groww.in/digest",
    }

    for endpoint in GROWW_ENDPOINTS:
        try:
            resp = requests.get(endpoint, headers=headers, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                word = (
                    data.get("word") or data.get("title") or
                    data.get("wordOfTheDay") or data.get("term") or ""
                )
                definition = (
                    data.get("definition") or data.get("description") or
                    data.get("meaning") or data.get("content") or ""
                )
                if word and definition:
                    logger.info(f"Word of the Day from Groww API: {word}")
                    return {"word": word, "definition": definition, "source": "Groww"}
        except Exception as e:
            logger.debug(f"Groww WOTD endpoint {endpoint} failed: {e}")

    # Fallback: rotate through curated list based on day of year
    day_index = date.today().timetuple().tm_yday % len(_WOTD_FALLBACK)
    word, definition = _WOTD_FALLBACK[day_index]
    logger.info(f"Word of the Day (fallback): {word}")
    return {"word": word, "definition": definition, "source": "Etica Finance Glossary"}